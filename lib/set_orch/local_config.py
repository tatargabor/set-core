"""Local, uncommitted configuration for machine- and project-specific values.

A committed file that needs a value specific to this machine or project — a
tools directory, a dev endpoint, a per-project token — reads it here instead
of inlining it, because an inlined value is exactly what the leak gate
(`set-leakscan --staged`) refuses at commit time. The gate's block message
points at this layer; this layer must therefore be ordinary to use, not a
research project.

Resolution order (most specific wins):

1. the environment variable ``SETCORE_<KEY>`` — upper-cased, every
   non-alphanumeric in ``key`` folded to an underscore;
2. the project-scoped file ``<config-dir>/projects/<project>.json``;
3. the machine-scoped file ``<config-dir>/config.json``;
4. the caller's default.

``<config-dir>`` mirrors ``bin/set-common.sh:get_config_dir()`` —
``SET_CONFIG_DIR`` overrides, then ``XDG_CONFIG_HOME``, then
``~/.config/set-core``. Nothing here ever writes inside a repository: values
live outside every tree the gate scans, which is the whole point.

A key missing at every level returns the default. That is an ordinary answer,
not an error — an unset value must not read as a failure, and code that needs
a value to exist says so at ITS call site, where the requirement is known.
"""

import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def config_dir() -> Path:
    """The set-core config directory. Mirrors set-common.sh:get_config_dir()."""
    override = os.environ.get("SET_CONFIG_DIR")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "set-core"
    return Path.home() / ".config" / "set-core"


def machine_file() -> Path:
    return config_dir() / "config.json"


def project_file(project: str) -> Path:
    return config_dir() / "projects" / f"{project}.json"


def default_project() -> str:
    """The project name for the current directory — the runtime's resolver.

    Callers that want cwd-scoping pass this to :func:`get`/:func:`set_value`;
    the module itself never guesses a project from the working directory,
    because an implicit scope is a value that silently changes meaning when a
    script is run from somewhere else.
    """
    from .paths import resolve_project_name

    return resolve_project_name()


def env_key(key: str) -> str:
    """The environment variable a key resolves from: `db_host` → `SETCORE_DB_HOST`."""
    return "SETCORE_" + re.sub(r"[^A-Za-z0-9]", "_", key).upper()


def _read_value(path: Path, key: str):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None          # absent or unreadable file reads as "unset" — not an error
    if isinstance(data, dict):
        return data.get(key)
    return None


def get(key: str, project: str | None = None, default=None):
    """Resolve a value through the chain. Unset at every level → `default`."""
    env = os.environ.get(env_key(key))
    if env is not None:
        return env
    if project:
        value = _read_value(project_file(project), key)
        if value is not None:
            return value
    value = _read_value(machine_file(), key)
    if value is not None:
        return value
    return default


def set_value(key: str, value, project: str | None = None) -> Path:
    """Write one key, MERGING into the existing file — never replacing it.

    Files are created owner-only (0600) inside an owner-only directory (0700):
    values here are frequently machine-private, and the layer would be a trap
    if writing one loosened the permissions around the others.

    Returns the file path written, so the CLI can show the user where the
    value actually landed.
    """
    path = project_file(project) if project else machine_file()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError):
        data = {}

    old = data.get(key)
    data[key] = value
    path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n",
                    encoding="utf-8")
    os.chmod(path, 0o600)
    os.chmod(path.parent, 0o700)
    logger.info("local_config: set %s%s (%r -> %r)", key,
                f" [{project}]" if project else "", old, value)
    return path


def entries(project: str | None = None) -> list[tuple[str, str, Path]]:
    """Every stored key as ``(key, value_type_and_shape, source_path)`` — never the value.

    The mask is deliberate and matches the leakscan `--list-patterns` precedent:
    a listing that prints values is a leak waiting for an innocent `list` in a
    shared terminal. The shape is enough to tell a string from a bool, which is
    all a listing is for.
    """
    found: list[tuple[str, str, Path]] = []
    paths: list[tuple[Path, str]] = [(machine_file(), "machine")]
    if project:
        paths.insert(0, (project_file(project), f"project:{project}"))

    seen: set[str] = set()
    for path, scope in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        for key in sorted(data):
            if key in seen:
                continue       # most specific source already reported it
            seen.add(key)
            value = data[key]
            shape = f"{type(value).__name__}({len(value)})" \
                if isinstance(value, str) else type(value).__name__
            found.append((key, shape, path))
    return found
