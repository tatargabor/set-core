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
    from .defaults import ANTHROPIC_MODEL_NAMES
    return list(ANTHROPIC_MODEL_NAMES)


def build(values: dict) -> dict:
    """The `providers.json` content a set of old keys translates into."""
    model = values["GLM_MODEL"]
    return {
        "version": 1,
        "default": {"provider": legacy.LEGACY_PROVIDER, "model": model},
        "providers": {
            # NO `model_ids` block: the shipped default applies and follows
            # every release. This used to write a full COPY of the table "so a
            # later change cannot move it" — which is exactly what stopped the
            # 2026-11-22 move of `sonnet`/`haiku` to 5.5 at the machine (B-191).
            # A deliberate pin is still possible: write the block by hand.
            "anthropic": {
                "models": _anthropic_models(),
                **_ANTHROPIC_DECL,
            },
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
        # The fresh-install case — no legacy file was ever there. Sending the
        # operator back to "create the config" is the loop this command's own
        # error message just came from; name the create path instead.
        raise ConfigError(
            f"nothing to migrate: {src} does not exist. This machine never had "
            "the legacy file — create the provider configuration directly "
            "instead (mode 0600; the JSON shape is documented in "
            "docs/reference/configuration.md, section 'Provider Configuration')"
        )
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


# ---------------------------------------------------------------- refresh

#: Classification of one entry in a machine's anthropic `model_ids` block.
CURRENT_COPY, STALE_COPY, OVERRIDE = "current-copy", "stale-copy", "override"


def classify_id(name: str, value: str) -> str:
    """A copy of what set-core ships now, a copy of what it shipped before, or the owner's own pin."""
    from .defaults import DEFAULT_MODEL_IDS, PREVIOUSLY_SHIPPED_IDS
    if DEFAULT_MODEL_IDS.get(name) == value:
        return CURRENT_COPY
    if value in PREVIOUSLY_SHIPPED_IDS.get(name, ()):
        return STALE_COPY
    return OVERRIDE


def stale_pins(declaration: dict) -> List[Tuple[str, str, str]]:
    """`[(name, copied_id, current_id)]` for each stale copy in an anthropic declaration."""
    from .defaults import DEFAULT_MODEL_IDS
    block = declaration.get("model_ids")
    if not isinstance(block, dict):
        return []
    return [(n, v, DEFAULT_MODEL_IDS[n]) for n, v in block.items()
            if isinstance(v, str) and classify_id(n, v) == STALE_COPY]


def refresh_plan(data: dict) -> Tuple[dict, List[str]]:
    """`(new_data, report_lines)` for the anthropic declaration; `new_data is data` when nothing changes."""
    from .defaults import ANTHROPIC_MODEL_NAMES, DEFAULT_MODEL_IDS
    decl = (data.get("providers") or {}).get("anthropic")
    if not isinstance(decl, dict):
        return data, ["no 'anthropic' provider declared — nothing to refresh"]
    new_decl = dict(decl)
    lines: List[str] = []

    block = decl.get("model_ids")
    if isinstance(block, dict):
        kinds = {n: classify_id(n, v) if isinstance(v, str) else OVERRIDE for n, v in block.items()}
        overrides = [n for n, k in kinds.items() if k == OVERRIDE]
        stale = [n for n, k in kinds.items() if k == STALE_COPY]
        if not overrides:
            del new_decl["model_ids"]
            lines.append(f"model_ids: every entry is a copy of a shipped value ({len(stale)} stale) — "
                         "removing the block, so the shipped default applies and follows releases")
            for n in stale:
                lines.append(f"  {n}: {block[n]} -> {DEFAULT_MODEL_IDS[n]}")
        else:
            ids = dict(block)
            for n in stale:
                ids[n] = DEFAULT_MODEL_IDS[n]
                lines.append(f"model_ids.{n}: stale copy {block[n]} -> {DEFAULT_MODEL_IDS[n]}")
            for n in overrides:
                lines.append(f"model_ids.{n}: kept — {block[n]!r} was never shipped for {n!r}, so it is a deliberate pin")
            missing = [n for n in DEFAULT_MODEL_IDS if n not in ids]
            for n in missing:
                ids[n] = DEFAULT_MODEL_IDS[n]
            if missing:
                lines.append(f"model_ids: added the shipped names the block lacked: {', '.join(missing)}")
            if ids != block:
                new_decl["model_ids"] = ids

    models = decl.get("models")
    if isinstance(models, list):
        add = [n for n in ANTHROPIC_MODEL_NAMES if n not in models]
        if add:
            new_decl["models"] = list(models) + add
            lines.append(f"models: added {', '.join(add)}")

    if new_decl == decl:
        return data, lines + ["anthropic declaration is up to date — nothing to change"]
    new_data = dict(data)
    new_data["providers"] = dict(data["providers"])
    new_data["providers"]["anthropic"] = new_decl
    return new_data, lines


def refresh(*, target: Optional[Path] = None, write: bool = False,
            now: Optional[str] = None) -> Tuple[bool, List[str]]:
    """Bring a machine file's copied id table along. Returns `(changed, report_lines)`.

    A dry run unless `write`. A write saves `<file>.bak-<stamp>` first and keeps
    the file's permission bits (the file can hold a credential).
    """
    import time
    dst = target or config_path()
    if not dst.exists():
        raise ConfigError(f"{dst} does not exist — nothing to refresh")
    raw = dst.read_bytes()
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ConfigError(f"{dst} is not valid JSON ({exc.msg}); fix it by hand first")
    new_data, lines = refresh_plan(data)
    if new_data is data:
        return False, lines
    if not write:
        return True, lines + ["dry run — re-run with --write to apply"]
    mode = stat.S_IMODE(dst.stat().st_mode)
    stamp = now or time.strftime("%Y%m%d-%H%M%S")
    backup = dst.with_name(f"{dst.name}.bak-{stamp}")
    for path, content in ((backup, raw), (dst, (json.dumps(new_data, indent=2) + "\n").encode())):
        tmp = path.with_name(path.name + ".tmp")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
        try:
            os.write(fd, content)
        finally:
            os.close(fd)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    logger.info("providers: refreshed %s (backup %s): %d change line(s)", dst, backup.name, len(lines))
    return True, lines + [f"wrote {dst} (mode {mode:04o}); backup {backup}"]
