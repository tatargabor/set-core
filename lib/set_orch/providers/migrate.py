"""`set-providers migrate` — the one act that converts the old file, on purpose.

## Why a command and not a fallback that fixes itself

Migrating on first read would be a WRITE hidden inside a resolver: it appears in
no trace, it fires in whichever process happens to read first, and the file it
produces was never reviewed by anyone. So the conversion is a named act a person
performs, and reading stays a pure read (there is a test that asserts the whole
package contains no write call at all).

## What it will not do

- **It does not delete the source.** A migration whose source is gone cannot be
  checked against its result, and the check is the point.
- **It does not overwrite an existing configuration** without being told to. It
  reports what it would change instead.
- **It does not print a secret.** The report names the fields it carried across;
  the values of the secret ones stay where they belong.
"""

from __future__ import annotations

import json
import logging
import os
import stat
from pathlib import Path
from typing import List, Optional, Tuple

from . import legacy
from .config import CONFIG_NAME, config_path, legacy_path
from .errors import ConfigError

logger = logging.getLogger(__name__)

#: Written for the provider the old file describes, and for the default one so a
#: migrated setup can switch back without editing by hand.
_ANTHROPIC_DECL = {
    "requires_credential": False,
    "credential": None,
    "default_model": "opus",
    "env": {},
    "args": [],
}


def _anthropic_models() -> List[str]:
    """The Anthropic catalogue, taken from the framework rather than retyped."""
    from ..config import ANTHROPIC_MODEL_NAMES
    return list(ANTHROPIC_MODEL_NAMES)


def build(values: dict) -> dict:
    """The `providers.json` content a set of old keys translates into."""
    model = values["GLM_MODEL"]
    return {
        "version": 1,
        "default": {"provider": legacy.LEGACY_PROVIDER, "model": model},
        "providers": {
            "anthropic": {"models": _anthropic_models(), **_ANTHROPIC_DECL},
            legacy.LEGACY_PROVIDER: {
                "models": [model],
                "requires_credential": True,
                "default_model": model,
                "credential": {
                    "token": values["GLM_TOKEN"],
                    "base_url": values.get("GLM_BASE_URL") or legacy.LEGACY_BASE_URL,
                },
                "env": dict(legacy.LEGACY_ENV),
                "args": list(legacy.LEGACY_ARGS),
            },
        },
        "projects": {},
    }


#: Which carried-across fields hold a secret. Named here so the report can say
#: what it moved without saying what it is.
_SECRET = {"GLM_TOKEN"}


def plan(values: dict) -> List[str]:
    """One line per field carried across — the field, never the value."""
    lines = []
    for key in sorted(values):
        lines.append(f"  {key} -> {'(value withheld)' if key in _SECRET else values[key]}")
    return lines


def migrate(
    *,
    source: Optional[Path] = None,
    target: Optional[Path] = None,
    overwrite: bool = False,
) -> Tuple[Path, List[str]]:
    """Convert, write owner-only, and report. Raises `ConfigError` saying why not.

    Returns `(written_path, report_lines)`.
    """
    src = source or legacy_path()
    dst = target or config_path()

    if not src.exists():
        raise ConfigError(f"nothing to migrate: {src} does not exist")
    values = legacy.read_legacy(src)
    for required in ("GLM_TOKEN", "GLM_MODEL"):
        if not values.get(required):
            raise ConfigError(f"{src}: {required} is missing; cannot migrate")

    if dst.exists() and not overwrite:
        raise ConfigError(
            f"{dst} already exists. Migrating would replace it. Review the two, then "
            f"re-run with --overwrite if that is what you want. Would carry across:\n"
            + "\n".join(plan(values))
        )

    content = json.dumps(build(values), indent=2) + "\n"
    dst.parent.mkdir(parents=True, exist_ok=True)

    # Create with the right mode from the start. Writing then chmod-ing leaves a
    # window in which the credential is world-readable, and a window is enough.
    fd = os.open(str(dst), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    try:
        os.write(fd, content.encode())
    finally:
        os.close(fd)
    os.chmod(dst, stat.S_IRUSR | stat.S_IWUSR)   # explicit for a pre-existing file

    logger.info("providers: migrated %s -> %s (%d field(s))", src, dst, len(values))
    report = [f"wrote {dst} (mode 0600)"] + plan(values) + [
        f"{src} left in place — check the result against it before removing it",
    ]
    return dst, report
