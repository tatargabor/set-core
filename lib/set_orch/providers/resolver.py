"""One resolver: project + request -> the environment, the argv and the PROVENANCE.

Every caller that launches an agent on a chosen provider goes through here —
`bin/set-glm` and the fleet's agent owner both. Not because duplication is
untidy, but because the launch parameters are measured values, and a measured
value that exists in two places drifts without either copy looking wrong.

## Precedence, and why the merge is hybrid

Three levels, in increasing priority:

    machine default  ->  project override  ->  this request

The MODEL resolves field-wise: the highest level that names one wins. That is
the whole point of a per-project setting — the model is precisely the thing
meant to differ per project.

The CREDENTIAL and its ENDPOINT resolve together, as one indivisible block. A
level that supplies either supplies both, or it is refused. A key is issued for
an endpoint; taking the key from one level and the endpoint from another is a
combination nobody wrote down, and it fails as a 401 at best and as the wrong
account at worst.

Both halves of that shape come from a peer's measured experience on the same
day, in both directions: field-wise merging saved them once, when a `reset
--hard` ate a configuration and they rebuilt it a key at a time — and the same
evening it produced a run whose model came from one source and whose remaining
settings came from another.

## Why provenance is returned rather than logged

After the fork, nothing on the process tree says which provider an agent runs
on, and a per-project credential means the level that won decides whose account
is billed. So the level that supplied each field is part of the RESULT: the
launch can print it, the screen can show it, and the record can keep it. An
agent silently running on another account is indistinguishable from outside,
which is the failure this design refuses to allow.

## Why every refusal happens here

Missing credential, unknown model, gateway-prefixed name: all refused before the
caller creates anything. Measured as B-105 in this repository — a child that
cannot start does not report "did not start". The scope never registers, the
wait spins out, and the caller is told "the scope did not become active" some
seconds later: a TRUE sentence about the symptom that points away from the
cause. A configuration fault has to be reported where it is still a
configuration fault.

And no refusal ever falls back to another provider. A silent fallback would run
the work in a different frame, on a different bill, with nothing saying so.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .config import MODEL_ALIASES, Credential, Provider, ProvidersConfig, load
from .errors import (
    IncompleteCredential, MissingCredential, UnknownModel, UnknownProvider,
)

logger = logging.getLogger(__name__)

#: The precedence levels, named so provenance is readable rather than numeric.
LEVEL_DEFAULT = "machine-default"
LEVEL_PROJECT = "project"
LEVEL_REQUEST = "request"
#: A value the PROVIDER declares for itself, distinct from the machine default.
#: Separate because provenance that says "machine-default" for a value the
#: machine default never named is a false value — the exact defect class this
#: whole result type exists to prevent, appearing inside the mechanism meant to
#: prevent it.
LEVEL_PROVIDER = "provider-default"

#: Credentials and endpoints belonging to a provider other than the resolved one.
#: Removed from every launch, unconditionally — including on the default
#: provider, where an inherited endpoint would otherwise redirect the call with
#: nothing on the screen saying so.
FOREIGN_KEYS: Tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
)

#: Environment keys whose VALUE is a credential. Named exactly, never matched as
#: a substring — measured while writing `set-glm --print-env`, a `"TOKEN" in key`
#: test masked `CLAUDE_CODE_MAX_CONTEXT_TOKENS`, printing `900000` as
#: `900000…0000 (6 chars)`. A substring test wearing the appearance of a rule is
#: still a substring test, and here it made a diagnostic lie in the direction of
#: looking careful.
SECRET_ENV_KEYS: Tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
)


def is_secret_env_key(key: str) -> bool:
    """Whether this key's value must never be printed. Exact match, by design."""
    return key in SECRET_ENV_KEYS


@dataclass(frozen=True)
class LaunchPlan:
    """Everything a caller needs to start a process, and where each part came from.

    `env` is applied on top of the child's environment; `unset` is removed from
    it FIRST. Two fields rather than one because a dict cannot express a removal,
    and the removal is not optional — see `FOREIGN_KEYS`.
    """

    provider: str
    model: str
    env: Dict[str, str]
    unset: Tuple[str, ...]
    args: Tuple[str, ...]
    #: field name -> the level that supplied it. Never contains a secret; the
    #: credential's entry names the LEVEL, which is the useful half.
    provenance: Dict[str, str] = field(default_factory=dict)

    def uses_default_credential(self) -> bool:
        """Whether the credential came from the machine default.

        The screen needs this to mark an agent spending against another account,
        and it must be answerable without the credential itself.
        """
        return self.provenance.get("credential", LEVEL_DEFAULT) == LEVEL_DEFAULT

    def launch_args(self, caller_args: Sequence[str] = ()) -> Tuple[str, ...]:
        """What to ADD to a caller's argv: the declared args, and the resolved model.

        ⚠ `model` is a resolved VALUE, and until 2026-08-29 it was the only part
        of a plan that no caller delivered. It reached the durable record, the
        API answer and the tile — and never the child's command line, so an agent
        started on a named provider ran that provider's endpoint with the CLI's
        DEFAULT model. Measured on a live agent: the owner reported
        `glm / glm-5.3-flash` while `/proc/<pid>/cmdline` read
        `claude --dangerously-skip-permissions --autocompact 700k`.

        **The fail direction is what makes it worth a method rather than a line
        at each call site.** Nothing errors: the endpoint accepts the request,
        the record is honest about what was ASKED for, and the only symptom is a
        model nobody chose answering under a name somebody did. The rule lived in
        exactly one caller (`bin/set-glm`), which is why the other two silently
        did without it. A plan that hands out its own arguments cannot be
        under-delivered by the next caller written.

        Returns only the ADDITIONS, so a caller appends rather than replaces, and
        a flag the caller already passed is never added twice — the caller's own
        value wins, which is what keeps `set-glm --model X` meaning what it says.

        ⚠ The model is translated to a CLI id on the way out, and skipping that
        would have made this method deliver a WRONG value rather than none — a
        worse defect than the one it fixes. The catalogue holds set-core's SHORT
        names (`opus-1m`, `opus-4-7-1m`), which are exactly `_MODEL_MAP`'s keys,
        while the CLI wants `claude-opus-4-6[1m]`. Every other caller that builds
        a `--model` already resolves first — `chat.py`, `subprocess_utils.py`,
        `category_resolver.py`, `engine.sh` — so this is the established
        convention, not a new rule. An unmapped name passes through unchanged,
        which is what keeps a provider whose catalogue holds real ids (`glm`)
        working without a second mapping table.
        """
        from ..subprocess_utils import resolve_model_id

        caller = set(caller_args)
        add: List[str] = []
        declared_flags = {a for a in self.args if a.startswith("--")}
        if not (declared_flags & caller):
            add += list(self.args)
        if self.model and "--model" not in caller and "--model" not in add:
            add += ["--model", resolve_model_id(self.model)]
        return tuple(add)

    def describe(self) -> str:
        """One line, safe to print anywhere. Names the endpoint, never the token.

        A frame switch has to be VISIBLE: without this line a run on another
        provider is indistinguishable from an ordinary one, and the next reader
        assigns its cost and its quality to the wrong frame.
        """
        where = self.env.get("ANTHROPIC_BASE_URL", "the CLI's own login")
        return (
            f"{self.provider}: {self.model} @ {where} "
            f"(provider from {self.provenance.get('provider', '?')}, "
            f"model from {self.provenance.get('model', '?')}, "
            f"credential from {self.provenance.get('credential', '?')})"
        )


def _check_model(provider: Provider, model: str) -> None:
    """The model must be in THIS provider's catalogue — not in a global list.

    Two separate refusals, because they need different messages. A gateway
    prefix is a specific, recurring mistake with a specific remedy, and saying
    only "unknown model" would leave the reader to spot the prefix themselves.
    """
    if "/" in model:
        raise UnknownModel(
            f"model {model!r} carries a gateway prefix. Provider {provider.name!r} is "
            f"reached at its native endpoint, which expects a bare name such as "
            f"{model.split('/')[-1]!r}. Measured response to the prefixed form: "
            "400 [1214][modelCode: does not exist]."
        )
    if model not in provider.models:
        raise UnknownModel(
            f"provider {provider.name!r} does not list model {model!r}. "
            f"Its catalogue is: {', '.join(provider.models)}"
        )


def _pick_credential(
    provider: Provider,
    override: Optional[Credential],
    override_level: str,
) -> Tuple[Optional[Credential], str]:
    """The credential and the level that supplied it — as one unit, never split."""
    if override is not None:
        return override, override_level
    return provider.credential, LEVEL_DEFAULT


def resolve(
    *,
    project: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    config: Optional[ProvidersConfig] = None,
) -> LaunchPlan:
    """Resolve a launch, or raise saying exactly what is wrong.

    `provider` and `model` are this request's values and outrank everything.
    `project` selects the override level. Nothing here reads the ambient
    environment: what a launch gets is decided by the configuration and the
    request, never by what happens to be exported in the calling shell.
    """
    cfg = config if config is not None else load()
    override = cfg.projects.get(project) if project else None

    # -- provider ------------------------------------------------------- #
    if provider:
        chosen, prov_level = provider, LEVEL_REQUEST
    elif override and override.provider:
        chosen, prov_level = override.provider, LEVEL_PROJECT
    elif cfg.default_provider:
        chosen, prov_level = cfg.default_provider, LEVEL_DEFAULT
    else:
        raise UnknownProvider(
            f"{cfg.source}: no provider requested and no 'default.provider' declared"
        )

    declared = cfg.providers.get(chosen)
    if declared is None:
        raise UnknownProvider(
            f"provider {chosen!r} is not declared in {cfg.source}. "
            f"Declared: {', '.join(cfg.provider_names())}"
        )

    # -- model ---------------------------------------------------------- #
    # ⚠ The machine-wide default model belongs to the machine's default PROVIDER.
    # Applying it to a different provider is the same defect the credential
    # pairing prevents, one axis over: a combination nobody wrote down. Measured
    # while wiring `set-glm`, which asks for the alternative provider and was
    # handed the default provider's model, then refused for a reason that named
    # the symptom rather than the fallback that produced it.
    if model:
        chosen_model, model_level = model, LEVEL_REQUEST
    elif override and override.model:
        chosen_model, model_level = override.model, LEVEL_PROJECT
    elif cfg.default_model and chosen == cfg.default_provider:
        chosen_model, model_level = cfg.default_model, LEVEL_DEFAULT
    elif declared.default_model:
        chosen_model, model_level = declared.default_model, LEVEL_PROVIDER
    else:
        raise UnknownModel(
            f"no model requested, and provider {chosen!r} declares no 'default_model'. "
            f"The machine default model is not used here: it belongs to provider "
            f"{cfg.default_provider!r}, and carrying it across would name a model "
            f"{chosen!r} does not have. Ask for one of: {', '.join(declared.models)}"
        )
    _check_model(declared, chosen_model)

    # -- credential, as one unit ---------------------------------------- #
    # An override's credential applies only to the provider it was written under.
    # Carrying it to a DIFFERENT provider would present a key to an endpoint it
    # was never issued for — the same wrong-account failure the pairing prevents.
    override_cred = None
    if override is not None and override.credential is not None:
        if override.provider in (None, chosen):
            override_cred = override.credential
        else:
            raise IncompleteCredential(
                f"project {project!r} declares a credential under provider "
                f"{override.provider!r}, but {chosen!r} was resolved. A credential "
                "belongs to one endpoint; it is not carried to another provider."
            )
    credential, cred_level = _pick_credential(declared, override_cred, LEVEL_PROJECT)

    # A provider that DECLARES it needs a credential and has none is refused here,
    # before the caller creates anything. Not inferred from the credential's
    # absence — see config.py: inferring it fails open, letting an unconfigured
    # provider reach its endpoint unauthenticated.
    if credential is None and declared.requires_credential:
        raise MissingCredential(
            f"provider {chosen!r} requires a credential and none is configured. "
            f"Add one under providers.{chosen}.credential in {cfg.source}"
            + (f", or under projects.{project}.credential" if project else "")
            + ". The launch is refused; it does NOT continue on another provider."
        )

    # -- the environment ------------------------------------------------ #
    env: Dict[str, str] = dict(declared.env)
    # The alias map, as environment. A subagent declared `model: sonnet` chooses
    # its model INSIDE the running CLI, so nothing this framework puts on a
    # command line can reach it — B-115. What it does inherit is the process
    # environment, which is why the map is delivered this way and not as argv.
    #
    # Emitted from the DECLARATION rather than written into the provider's `env`
    # by hand, so the targets are checked against that provider's own catalogue
    # at load time. Hand-written variables are accepted unvalidated, and the only
    # symptom of a typo is one subagent quietly answering from a fallback.
    emitted: Set[str] = set()
    for alias, target in sorted(declared.model_aliases.items()):
        env[MODEL_ALIASES[alias]] = target
        emitted.add(MODEL_ALIASES[alias])
    if credential is not None:
        env["ANTHROPIC_BASE_URL"] = credential.base_url
        env["ANTHROPIC_AUTH_TOKEN"] = credential.token

    provenance = {
        "provider": prov_level,
        "model": model_level,
        "credential": cred_level if credential is not None else LEVEL_DEFAULT,
        "env": LEVEL_DEFAULT,
    }

    plan = LaunchPlan(
        provider=chosen,
        model=chosen_model,
        env=env,
        # An alias variable this provider does not declare is removed from the
        # child exactly like a foreign credential — B-116. Both start paths build
        # the child's environment from the AMBIENT environment (`bin/set-glm`
        # from `os.environ`, the owner from a caller-supplied mapping), so an
        # exported `ANTHROPIC_DEFAULT_OPUS_MODEL` from an unrelated session would
        # otherwise survive into a launch on a provider that declares no `opus`
        # alias, and a subagent would send an Anthropic id at this endpoint —
        # B-115's symptom, through a path B-115's fix does not close. The rule is
        # the same one FOREIGN_KEYS carries: what reaches the child is decided by
        # the configuration and the request, never by the calling shell.
        # Invariants this relies on: MODEL_ALIASES values are unique and
        # disjoint from FOREIGN_KEYS, and a key the provider hand-wrote in its
        # own `env` is a DELIBERATE declaration — it is excluded here, or a
        # caller applying unset-first would strip what the configuration
        # declared (measured by review, 2026-08-29).
        unset=FOREIGN_KEYS
        + tuple(k for k in MODEL_ALIASES.values()
                if k not in emitted and k not in declared.env),
        args=declared.args,
        provenance=provenance,
    )
    logger.info("providers: resolved %s", plan.describe())
    return plan


def catalogue(config: Optional[ProvidersConfig] = None) -> Dict[str, object]:
    """What a surface may be told: names, models, and whether each is usable.

    ⚠ This is a SEPARATELY NAMED exit, not `resolve` with a redaction flag, and
    that is deliberate. A flag has a default, and a default that flips the wrong
    way publishes a token. This function's return value has no field a credential
    could occupy, so there is no argument anyone can get wrong.

    An unusable provider is LISTED rather than omitted. A provider that silently
    disappears leaves a person no way to find out why they cannot choose it —
    the same reason a gap must not render as a zero.
    """
    cfg = config if config is not None else load()
    return {
        "default": {"provider": cfg.default_provider, "model": cfg.default_model},
        "providers": [
            {
                "name": p.name,
                "models": list(p.models),
                "usable": p.is_usable(),
                "reason": None if p.is_usable() else "no credential configured",
            }
            for p in (cfg.providers[n] for n in cfg.provider_names())
        ],
    }
