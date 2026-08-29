"""The provider configuration: one machine-level file, read and validated.

## The file

`~/.config/set-core/providers.json`, honouring `XDG_CONFIG_HOME`. Mode `0600`,
and this module REFUSES to read it if the mode says otherwise — it holds
credentials, and a file that has quietly become group-readable is exactly the
state a check exists to catch.

It sits beside the central configuration this machine already keeps
(`config.json`, `cc-accounts.json`, `projects.json`), all of which are already
`0600`. Every set project inherits it by READING it. Nothing copies it into a
project tree, and the deploy path must never write one: a credential inside a
working tree is removed by a `reset --hard` and republished by a careless `add`.

## The shape

    {
      "version": 1,
      "default": {"provider": "anthropic", "model": "opus"},
      "providers": {
        "anthropic": {
          "models": ["haiku", "sonnet", "opus"],
          "requires_credential": false,
          "credential": null,
          "env": {},
          "args": []
        },
        "glm": {
          "models": ["glm-5.3", "glm-5.3-flash"],
          "requires_credential": true,
          "credential": {
            "token": "...",
            "base_url": "https://api.z.ai/api/anthropic"
          },
          "env": {"CLAUDE_CODE_MAX_CONTEXT_TOKENS": "900000"},
          "args": ["--autocompact", "700k"]
        }
      },
      "projects": {
        "some-project": {
          "provider": "glm",
          "model": "glm-5.3",
          "credential": {"token": "...", "base_url": "..."}
        }
      }
    }

**`requires_credential` is declared, never inferred.** It would be tempting to
read "has a credential" as "needs one" — but then a provider whose token has not
been filled in yet looks exactly like one that uses the CLI's own login, and the
launch proceeds to an endpoint with no authentication. That is a fail-OPEN
inference, and the direction is what makes it worth a required field: with the
flag, an unconfigured provider is *unusable and says so*; without it, it is
*silently wrong*.

So `requires_credential: true` with `credential: null` is a legitimate,
meaningful state — declared but not yet configured — and it is what the surface
shows as unusable rather than hiding. `requires_credential: false` means the
provider uses the CLI's own login.

Both keys are REQUIRED on every declaration. An omitted key is an unfinished
declaration and is refused by name, rather than defaulted into whichever
behaviour happens to be safer to code.

**`env` and `args` are DATA.** They are the measured launch parameters, and they
live here so that adding a model, or correcting a parameter, costs no framework
change and no redeploy. The values shipped for the alternative provider were
re-measured independently on 2026-08-29 — a control run establishing the wall,
then each variant — and the appendix of this change's `design.md` carries the
table. A redundant variable is deliberately NOT set: it would only obscure which
one acts.
"""

from __future__ import annotations

import json
import logging
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .errors import ConfigError

logger = logging.getLogger(__name__)

#: The file name, beside the rest of this machine's set-core configuration.
CONFIG_NAME = "providers.json"

#: The single-provider file this one replaces, still read for one release.
LEGACY_NAME = "glm.env"


def config_dir() -> Path:
    """Where this machine keeps its set-core configuration.

    `SET_CONFIG_DIR` first because `lib/set_router` already honours it and a test
    that can only redirect one of the two would be measuring half the system.
    """
    override = os.environ.get("SET_CONFIG_DIR")
    if override:
        return Path(override)
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "set-core"


def config_path() -> Path:
    return config_dir() / CONFIG_NAME


def legacy_path() -> Path:
    return config_dir() / LEGACY_NAME


@dataclass(frozen=True)
class Credential:
    """A token and the endpoint it authenticates against — one unit, never split."""

    token: str
    base_url: str


@dataclass(frozen=True)
class Provider:
    """One declared provider: how to reach it, and what it will answer to."""

    name: str
    models: Tuple[str, ...]
    #: Declared, not inferred — see the module docstring on the fail-open this
    #: avoids. True and `credential is None` means "declared, not yet configured".
    requires_credential: bool
    #: `None` means either "uses the CLI's own login" or "not configured yet";
    #: `requires_credential` is what tells those two apart.
    credential: Optional[Credential]
    #: Measured launch parameters, as data.
    env: Dict[str, str]
    args: Tuple[str, ...]

    def is_usable(self) -> bool:
        """Whether an agent can actually be started on this provider right now."""
        return self.credential is not None or not self.requires_credential


@dataclass(frozen=True)
class ProjectOverride:
    """What one project changes about the machine default."""

    provider: Optional[str] = None
    model: Optional[str] = None
    credential: Optional[Credential] = None


@dataclass(frozen=True)
class ProvidersConfig:
    """The whole file, validated."""

    providers: Dict[str, Provider]
    default_provider: Optional[str]
    default_model: Optional[str]
    projects: Dict[str, ProjectOverride]
    #: Where it came from. Carried so a diagnostic can name the file the reader
    #: must edit, rather than the path this module happens to think is default.
    source: Path

    def provider_names(self) -> List[str]:
        return sorted(self.providers)


def _require_owner_only(path: Path) -> None:
    """Refuse a configuration file any other user can read.

    Fails rather than warns. A warning on a credential file is a line in a log
    nobody reads, and the state it describes does not repair itself.
    """
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ConfigError(
            f"{path} is mode {mode:04o}; it holds credentials and must be owner-only. "
            f"Fix it with: chmod 600 {path}"
        )


def _credential(raw: object, where: str) -> Optional[Credential]:
    """Read a credential block, insisting it is whole.

    `None` is legitimate — the provider uses the CLI's own login. A dict missing
    either half is not: half a pair from one place and half from another is the
    combination that authenticates against the wrong account.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: 'credential' must be an object or null")
    token, base_url = raw.get("token"), raw.get("base_url")
    missing = [k for k, v in (("token", token), ("base_url", base_url)) if not v]
    if missing:
        raise ConfigError(
            f"{where}: 'credential' is missing {', '.join(missing)}. A token and the "
            "endpoint it authenticates against are one unit; supply both or neither."
        )
    return Credential(token=str(token), base_url=str(base_url))


def _provider(name: str, raw: object, source: Path) -> Provider:
    where = f"{source}: provider {name!r}"
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: declaration must be an object")

    models = raw.get("models")
    if not isinstance(models, list) or not models or not all(isinstance(m, str) for m in models):
        raise ConfigError(f"{where}: 'models' must be a non-empty list of names")

    # Present-but-null and absent are DIFFERENT answers here, and so is the flag
    # beside it. See the module docstring on the fail-open that inferring one
    # from the other would produce.
    if "credential" not in raw:
        raise ConfigError(
            f"{where}: 'credential' is required. Use null when the provider uses the "
            "CLI's own login or is not configured yet; an omitted key reads as an "
            "unfinished declaration."
        )
    if not isinstance(raw.get("requires_credential"), bool):
        raise ConfigError(
            f"{where}: 'requires_credential' is required and must be true or false. "
            "It is declared rather than inferred because a provider awaiting its "
            "token would otherwise be indistinguishable from one that needs none, "
            "and the launch would reach an endpoint unauthenticated."
        )

    env = raw.get("env", {})
    if not isinstance(env, dict) or not all(
        isinstance(k, str) and isinstance(v, (str, int)) for k, v in env.items()
    ):
        raise ConfigError(f"{where}: 'env' must be an object of string keys to scalar values")

    args = raw.get("args", [])
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        raise ConfigError(f"{where}: 'args' must be a list of strings")

    return Provider(
        name=name,
        models=tuple(models),
        requires_credential=raw["requires_credential"],
        credential=_credential(raw["credential"], where),
        env={k: str(v) for k, v in env.items()},
        args=tuple(args),
    )


def _project(name: str, raw: object, source: Path) -> ProjectOverride:
    where = f"{source}: project {name!r}"
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: override must be an object")
    provider = raw.get("provider")
    model = raw.get("model")
    if provider is not None and not isinstance(provider, str):
        raise ConfigError(f"{where}: 'provider' must be a name")
    if model is not None and not isinstance(model, str):
        raise ConfigError(f"{where}: 'model' must be a name")
    return ProjectOverride(
        provider=provider,
        model=model,
        credential=_credential(raw.get("credential"), where),
    )


def load(path: Optional[Path] = None) -> ProvidersConfig:
    """Read and validate the configuration, or raise `ConfigError` saying why.

    Every failure names the file and the specific fault. In particular a file
    that cannot be parsed raises rather than yielding an empty configuration:
    "no providers are declared" and "I could not read the declarations" lead an
    operator to different places, and only one of them is true.
    """
    src = path or config_path()
    if not src.exists():
        raise ConfigError(
            f"no provider configuration at {src}. Create one, or migrate an existing "
            f"{LEGACY_NAME} with: set-providers migrate"
        )
    _require_owner_only(src)

    try:
        raw = json.loads(src.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{src} is malformed JSON: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"{src} could not be read: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"{src}: top level must be an object")

    declared = raw.get("providers")
    if not isinstance(declared, dict) or not declared:
        raise ConfigError(f"{src}: 'providers' must be a non-empty object")

    providers = {name: _provider(name, decl, src) for name, decl in declared.items()}

    default = raw.get("default") or {}
    if not isinstance(default, dict):
        raise ConfigError(f"{src}: 'default' must be an object")

    projects_raw = raw.get("projects") or {}
    if not isinstance(projects_raw, dict):
        raise ConfigError(f"{src}: 'projects' must be an object keyed by project name")
    projects = {name: _project(name, decl, src) for name, decl in projects_raw.items()}

    logger.debug(
        "providers: loaded %s — %d provider(s) %s, %d project override(s)",
        src, len(providers), sorted(providers), len(projects),
    )
    return ProvidersConfig(
        providers=providers,
        default_provider=default.get("provider"),
        default_model=default.get("model"),
        projects=projects,
        source=src,
    )
