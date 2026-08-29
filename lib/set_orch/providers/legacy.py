"""The single-provider configuration this package replaces, read for one release.

## What it was

`~/.config/set-core/glm.env` — a flat `KEY=value` file holding one provider's
token, model and endpoint. It worked, and the setups that use it must not break
on the day `providers.json` ships.

## Why reading it is a compatibility path and not a design

It can express exactly one provider, has no notion of a project, and cannot say
which precedence level supplied anything. Synthesising a `ProvidersConfig` from
it therefore produces a configuration with one provider and no overrides — which
is the honest translation, not a degraded one.

## The window, and why closing it is one edit

`WINDOW_OPEN` below is the single switch. While it is true, a setup with only the
old file keeps working and is warned every time. When it is set to false, the old
file stops being read and the failure NAMES THE MIGRATION COMMAND — it does not
say "no provider is configured", because that sentence sends an operator to
create something they already have.

That distinction is the same one this repository keeps paying for elsewhere: a
gap is not a zero, and "I could not read your configuration" is not "you have
none".
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, Optional

from .config import (
    CONFIG_NAME, Credential, Provider, ProvidersConfig, config_path, legacy_path,
)
from .errors import ConfigError

logger = logging.getLogger(__name__)

#: The one switch that closes the deprecation window. Flip it to False in the
#: release after `providers.json` ships; nothing else needs editing.
WINDOW_OPEN = True

#: The provider name the old file is understood to describe.
LEGACY_PROVIDER = "glm"

#: The measured launch parameters the old file never carried, applied to the
#: provider synthesised from it so a migrated-by-compatibility run behaves like a
#: migrated-for-real one. Re-measured independently 2026-08-29 — the appendix of
#: this change's design.md holds the table and the control run.
LEGACY_ENV: Dict[str, str] = {"CLAUDE_CODE_MAX_CONTEXT_TOKENS": "900000"}
LEGACY_ARGS = ("--autocompact", "700k")
LEGACY_BASE_URL = "https://api.z.ai/api/anthropic"

_LINE = re.compile(r"^\s*(GLM_[A-Z0-9_]+)\s*=(.*)$")


def read_legacy(path: Optional[Path] = None) -> Dict[str, str]:
    """The `GLM_*` keys of the old file, or an empty mapping if it is not there.

    ⚠ Only `GLM_`-prefixed lines, deliberately. Sourcing the whole file would
    also import an `ANTHROPIC_API_KEY` sitting in it — the very key that would
    redirect the call to another account, silently. What is not read cannot leak.
    """
    src = path or legacy_path()
    if not src.exists():
        return {}
    out: Dict[str, str] = {}
    for line in src.read_text().splitlines():
        m = _LINE.match(line)
        if not m:
            continue
        value = m.group(2).strip().strip('"').strip("'")
        out[m.group(1)] = value
    return out


def as_config(values: Dict[str, str], source: Path) -> ProvidersConfig:
    """Translate the old file's keys into the shape the resolver understands."""
    token = values.get("GLM_TOKEN")
    model = values.get("GLM_MODEL")
    if not token:
        raise ConfigError(f"{source}: GLM_TOKEN is missing")
    if not model:
        raise ConfigError(f"{source}: GLM_MODEL is missing")
    provider = Provider(
        name=LEGACY_PROVIDER,
        models=(model,),
        requires_credential=True,
        default_model=model,
        credential=Credential(
            token=token, base_url=values.get("GLM_BASE_URL") or LEGACY_BASE_URL
        ),
        env=dict(LEGACY_ENV),
        args=LEGACY_ARGS,
    )
    return ProvidersConfig(
        providers={LEGACY_PROVIDER: provider},
        default_provider=LEGACY_PROVIDER,
        default_model=model,
        projects={},
        source=source,
    )


def deprecation_notice(source: Path) -> str:
    return (
        f"{source} is deprecated and will stop being read in the next release. "
        f"Move it with: set-providers migrate   (it writes {config_path()} and "
        f"leaves {source.name} in place)"
    )


def closed_window_error(source: Path) -> str:
    """The message after the window closes.

    It must not read as "nothing is configured": an operator who has a `glm.env`
    and is told they have no provider goes and creates a second one.
    """
    return (
        f"{source} is no longer read — the deprecation window has closed. Your "
        f"provider IS configured, in a file this version does not consult. "
        f"Convert it with: set-providers migrate   (writes {CONFIG_NAME})"
    )
