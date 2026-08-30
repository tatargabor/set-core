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
          "default_model": "opus",
          "env": {},
          "args": []
        },
        "glm": {
          "models": ["glm-5.3", "glm-5.3-flash"],
          "requires_credential": true,
          "default_model": "glm-5.3-flash",
          "credential": {
            "token": "...",
            "base_url": "https://api.z.ai/api/anthropic"
          },
          "env": {"CLAUDE_CODE_MAX_CONTEXT_TOKENS": "900000"},
          "args": ["--autocompact", "700k"],
          "model_aliases": {"sonnet": "glm-5.3", "haiku": "glm-5.3"}
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

**`model_aliases` is how a SUBAGENT reaches the right model.** A subagent
declared `model: sonnet` chooses inside the running CLI, after launch, so no
argv this framework builds can reach it — the process environment is the only
carrier. Each entry becomes one `ANTHROPIC_DEFAULT_<ALIAS>_MODEL` variable.
Targets are checked against this provider's own catalogue at load time, because
setting those variables by hand accepts any string and fails silently: measured
2026-08-29, an invalid target produced nothing but one `unrecognized_model` line
inside a single subagent's output.

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
from dataclasses import dataclass, field
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


#: The model ALIASES a Claude Code process resolves in-process, and the
#: environment variable that redirects each one. This is the whole reason a
#: `model_aliases` block can work at all: a subagent defined with
#: `model: sonnet` picks its model INSIDE the running CLI, after launch, so no
#: argv this framework builds can reach it — but the environment it inherits can.
#: Measured 2026-08-29 against Claude Code 2.1.251 by pointing the sonnet alias
#: at a name that does not exist: the CLI reported
#: `unrecognized_model {"model": "<that name>"}` and made no API call, which is
#: the proof the alias was rewritten rather than ignored.
MODEL_ALIASES: Dict[str, str] = {
    "haiku": "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "sonnet": "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "opus": "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "fable": "ANTHROPIC_DEFAULT_FABLE_MODEL",
}


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
    #: The model this provider falls back to when nothing else named one. It
    #: exists because a machine-wide default model belongs to the machine's
    #: default PROVIDER: applying it to a different provider produces exactly the
    #: cross-provider combination this design refuses everywhere else.
    default_model: Optional[str]
    #: Measured launch parameters, as data.
    env: Dict[str, str]
    args: Tuple[str, ...]
    #: alias -> one of this provider's OWN models. Declared per provider rather
    #: than per project, because it is a statement about that provider's
    #: catalogue, not about a piece of work. Empty means "this provider answers
    #: to the aliases directly", which is true of `anthropic` and of nothing else.
    model_aliases: Dict[str, str] = field(default_factory=dict)

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

    fallback = raw.get("default_model")
    if fallback is not None and fallback not in models:
        raise ConfigError(
            f"{where}: 'default_model' is {fallback!r}, which is not in this "
            f"provider's own catalogue ({', '.join(models)})"
        )

    args = raw.get("args", [])
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        raise ConfigError(f"{where}: 'args' must be a list of strings")

    # `model_aliases` is validated at LOAD time, against this provider's own
    # catalogue, because the alternative is silent. Setting the underlying
    # environment variable by hand accepts any string at all — measured: a
    # deliberately invalid name was taken without complaint, and the only symptom
    # was a `unrecognized_model` line inside one subagent's output. A refusal
    # naming the file and the catalogue is the whole point of declaring it here
    # rather than writing the variables directly.
    aliases = raw.get("model_aliases", {})
    if not isinstance(aliases, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in aliases.items()
    ):
        raise ConfigError(f"{where}: 'model_aliases' must be an object of alias -> model name")
    for alias, target in aliases.items():
        if alias not in MODEL_ALIASES:
            raise ConfigError(
                f"{where}: 'model_aliases' names {alias!r}, which is not an alias the CLI "
                f"resolves. Known aliases: {', '.join(sorted(MODEL_ALIASES))}"
            )
        if target not in models:
            raise ConfigError(
                f"{where}: 'model_aliases.{alias}' is {target!r}, which is not in this "
                f"provider's own catalogue ({', '.join(models)}). An alias may only point at "
                f"a model this provider actually serves — pointing it elsewhere is the "
                f"cross-provider pair this design refuses everywhere else."
            )

    return Provider(
        name=name,
        models=tuple(models),
        requires_credential=raw["requires_credential"],
        default_model=raw.get("default_model"),
        credential=_credential(raw["credential"], where),
        env={k: str(v) for k, v in env.items()},
        args=tuple(args),
        model_aliases={k: str(v) for k, v in aliases.items()},
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


def load_or_legacy() -> Tuple[ProvidersConfig, Optional[str]]:
    """The configuration, plus a notice to show the operator if one applies.

    The order is what makes the deprecation honest: `providers.json` wins
    whenever it exists, so a migrated setup goes quiet immediately rather than
    warning about a file it no longer depends on.

    Returns `(config, notice_or_None)`. The notice is returned rather than
    printed because this package must not choose an output stream for its
    callers — a CLI writes it to stderr, a service logs it, and neither should
    have the other's behaviour forced on it.
    """
    from . import legacy                      # local: legacy imports from here

    primary = config_path()
    if primary.exists():
        return load(primary), None

    src = legacy_path()
    if src.exists():
        if not legacy.WINDOW_OPEN:
            raise ConfigError(legacy.closed_window_error(src))
        _require_owner_only(src)
        return legacy.as_config(legacy.read_legacy(src), src), legacy.deprecation_notice(src)

    # Neither exists. Name both, because an operator who has never configured
    # this and one whose file is somewhere unexpected need different next steps.
    # A FRESH INSTALL is the first case, and "create it" without the shape is a
    # dead end — measured 2026-08-30 on a third machine: the suggested migrate
    # then answered "nothing to migrate". Name the documented shape instead.
    raise ConfigError(
        f"no provider configuration: neither {primary} nor {src} exists. "
        "Create the first by hand (mode 0600; the JSON shape is documented in "
        "docs/reference/configuration.md, section 'Provider Configuration'), "
        "or run: set-providers migrate — but only if an older glm.env exists"
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
            f"no provider configuration at {src}. Create one by hand (mode 0600; "
            "the JSON shape is documented in docs/reference/configuration.md, "
            f"section 'Provider Configuration'), or migrate an existing "
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
