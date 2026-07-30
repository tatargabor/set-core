from __future__ import annotations

"""Gate profiles — per-change-type verification gate configuration.

Resolves which gates run for each change based on:
1. Universal defaults for all gate types
2. Universal per-change_type defaults
3. Profile-registered gate defaults
4. Profile gate_overrides()
5. Per-change explicit overrides from plan
6. Orchestration directive overrides
"""

from typing import Optional
import logging

logger = logging.getLogger(__name__)


class GateConfig:
    """Resolved gate configuration for a single change.

    Stores gate modes as a dict[str, str] supporting arbitrary gate names.
    Non-gate attributes (test_files_required, max_retries, etc.) are direct attrs.

    **Every attribute, by name.** `_gates`, `test_files_required`, `max_retries`,
    `review_model`, `review_extra_retries`.

    The gate modes live in `_gates` — note the underscore. Read them through
    `should_run()` / `is_blocking()` / `is_warn_only()` / `get()` / `gate_names()`, which is
    why the attribute is private; but a caller who reaches for `getattr(cfg, "gates", {})`
    gets an empty dict rather than an error, and an empty gate map reads as "nothing
    configured" instead of "I spelled it wrong". Measured on an integration peer, who hit
    exactly this — the third instance that day of the same class (`j.bugs` under an
    envelope, `read_commands` for `commands`, then `gates` for `_gates`).

    The general rule, theirs: **enumerate a foreign object's fields before reading one by
    name** (`dataclasses.fields(o)`, `vars(o)`, `Object.keys(o)`). The obligation on this
    side is the list above, kept in step by `test_gate_config_docstring_names_every_attr`.
    """

    def __init__(self, gates: dict[str, str] | None = None, **kwargs):
        self._gates: dict[str, str] = dict(gates) if gates else {}
        self.test_files_required: bool = kwargs.get("test_files_required", True)
        self.max_retries: Optional[int] = kwargs.get("max_retries")
        self.review_model: Optional[str] = kwargs.get("review_model")
        self.review_extra_retries: int = kwargs.get("review_extra_retries", 1)

    def should_run(self, gate_name: str) -> bool:
        """Whether a gate should execute at all."""
        val = self._gates.get(gate_name, "run")
        return val in ("run", "warn", "soft")

    def is_blocking(self, gate_name: str) -> bool:
        """Whether gate failure should block merge."""
        return self._gates.get(gate_name, "run") == "run"

    def is_warn_only(self, gate_name: str) -> bool:
        """Whether gate failure is warning-only (non-blocking)."""
        val = self._gates.get(gate_name, "run")
        return val in ("warn", "soft")

    def get(self, gate_name: str, default: str = "run") -> str:
        """Get gate mode by name."""
        return self._gates.get(gate_name, default)

    def set(self, gate_name: str, mode: str) -> None:
        """Set gate mode by name."""
        self._gates[gate_name] = mode

    def gate_names(self) -> list[str]:
        """Return all configured gate names."""
        return list(self._gates.keys())


# ── Universal defaults per change_type (universal gates only) ──────

UNIVERSAL_DEFAULTS: dict[str, dict[str, str]] = {
    "infrastructure": {
        "build": "skip",
        "test": "skip",
        "e2e": "skip",
        "scope_check": "run",
        "test_files": "skip",
        "review": "run",
        "rules": "warn",
        "spec_verify": "soft",
    },
    "schema": {
        "build": "run",
        "test": "warn",
        "scope_check": "run",
        "test_files": "run",
        "review": "run",
        "rules": "warn",
        "spec_verify": "run",
    },
    "foundational": {
        "build": "run",
        "test": "run",
        "scope_check": "run",
        "test_files": "run",
        "review": "run",
        "rules": "warn",
        "spec_verify": "run",
    },
    "feature": {
        "build": "run",
        "test": "run",
        "scope_check": "run",
        "test_files": "run",
        "review": "run",
        "rules": "warn",
        "spec_verify": "run",
    },
    # ── The cheaper entrance, and its delta stated where the profile lives ──
    #
    # **The delta against `feature`, in one line: `test_files` stops blocking.** Everything
    # else is byte-identical to `feature` on purpose, and the difference is deliberately ONE
    # gate rather than a bundle, because a bundle cannot be argued for or against.
    #
    # Why that gate and no other. `test_files` asks "did this change add test files?", which is
    # a PROXY for "is this change tested". A conditional lane is only granted when the project
    # runs a blocking exit obligation — a signal that fires when a fixed defect has no test
    # citing it — and that measures the thing itself. So the entrance drops the proxy exactly
    # where the exit measures the real property. This repo's own rule book calls measuring a
    # proxy instead of the thing a defect class; here it is the trade being made explicit.
    #
    # What is deliberately NOT softened, and this is the load-bearing restraint: `spec_verify`
    # stays blocking. The tempting argument is that a fix restores what the specification
    # already says, so there is no delta to verify — but that is precisely the entrance
    # question the design refuses to gate on (D4), because the most advanced practice available
    # measured itself at 9.3% and asked that the half it demonstrably does not keep not be
    # generalised. Softening `spec_verify` on that assumption would loosen the one check that
    # catches the assumption being wrong, which is the reassuring direction.
    #
    # A profile equal to another profile is a false gate: it reads as meaning something and
    # means nothing. `feature` and `foundational` are byte-identical in this very dictionary
    # and nobody noticed until it was measured, which is why
    # `test_the_bugfix_profile_differs_from_every_other_one` exists.
    "bugfix": {
        "build": "run",
        "test": "run",
        "scope_check": "run",
        "test_files": "warn",
        "review": "run",
        "rules": "warn",
        "spec_verify": "run",
    },
    "cleanup-before": {
        "build": "run",
        "test": "warn",
        "scope_check": "run",
        "test_files": "run",
        "review": "run",
        "rules": "warn",
        "spec_verify": "soft",
    },
    "cleanup-after": {
        "build": "run",
        "test": "warn",
        "scope_check": "run",
        "test_files": "run",
        "review": "skip",
        "rules": "skip",
        "spec_verify": "soft",
    },
}

# Non-gate attributes per change_type
_CHANGE_TYPE_ATTRS: dict[str, dict] = {
    "infrastructure": {"test_files_required": False},
    "schema": {"test_files_required": False},
    # The other half of the one-gate delta: softening `test_files` to "warn" without this would
    # leave the requirement enforced by a different attribute, so the discount would be
    # announced and not delivered — a marker true of a narrower subject than its reader takes
    # it for. Paid for by the exit obligation, exactly as the gate mode is.
    "bugfix": {"test_files_required": False},
    "cleanup-before": {"test_files_required": False},
    "cleanup-after": {"test_files_required": False},
}


#: Change types whose ENTRY is conditional: declaring one is refused unless the project
#: declares an enforced exit obligation for it (`change_type_lanes.require_exit_obligation`).
#:
#: A set rather than a hard-coded `== "bugfix"` so that the mechanism is one thing and its
#: membership another — but deliberately a set of ONE. The 2026-07-19 verdict's ordering
#: constraint is that a differentiated pipeline is built first and alone, and a taxonomy comes
#: only once two provably different pipelines exist to choose between. Adding a second name
#: here without a second delta would be the false gate that verdict names.
CONDITIONAL_CHANGE_TYPES: frozenset[str] = frozenset({"bugfix"})


# ── The set of valid change types — ONE home ────────────────────────
#
# `UNIVERSAL_DEFAULTS` above IS the definition: a type exists exactly when it has a gate
# profile, which is the only thing a type *is* here. Everything else derives.
#
# Measured before this was written, and the figure in the change's own artifacts was
# UNDER-counted — it said three places, which is the completeness-claim-is-a-summary class
# arriving in the document that warns about it. The verbatim enum string
# (the six names joined by pipes) had **five** live copies outside tests and specs:
# four in `templates.py` (planner prompts) and one in the deployed decompose skill, plus
# prose restatements in `templates.py`, `plan-review.md` and `profile_types.py`, plus
# `merger.py`'s exemption tuple naming two types that exist nowhere else.
#
# Declaration order, NOT sorted, and that is load-bearing rather than incidental: the enum
# is read by a planning agent, and the dict's order groups the types the way the pipeline
# uses them (setup → schema → shared → feature → cleanup). `"|".join(valid_change_types())`
# therefore reproduced the historical string byte-for-byte at the moment of substitution,
# which is what made the substitution provably inert instead of merely plausible.


def valid_change_types() -> tuple[str, ...]:
    """The valid change types, in declaration order.

    Derived, never restated. A component that needs the list calls this; a component that
    writes the list out by hand is a second copy, and the second copy is the one that
    drifts — see `test_change_type_list_has_one_home`.
    """
    return tuple(UNIVERSAL_DEFAULTS)


def is_valid_change_type(name: str) -> bool:
    """Whether `name` is a change type this set-core version defines."""
    return name in UNIVERSAL_DEFAULTS


def change_type_enum() -> str:
    """The pipe-separated enum, for prompts and templates that must show the choices.

    Exists so a prompt can *contain* the list without *holding* it. Four planner prompts
    and one deployed skill file carried this string by hand; a type added to the dictionary
    reached none of them.
    """
    return "|".join(valid_change_types())


def resolve_gate_config(
    change,
    profile=None,
    directives: dict | None = None,
    tree=None,
) -> GateConfig:
    """Resolve the gate configuration for a change.

    Resolution chain (later layers override earlier):
    0. A conditional change type's entry condition — raises `ConditionalLaneRefused`
    1. Universal gate defaults (all "run")
    2. Universal per-change_type defaults
    3. Profile-registered gate defaults (register_gates)
    4. Profile gate_overrides()
    5. Per-change skip flags + gate_hints
    6. Orchestration directive overrides

    `tree` is the worktree being verified. It is only read for a conditional change type, and
    its absence is a refusal rather than a grant — see `require_exit_obligation`.
    """
    change_type = getattr(change, "change_type", None) or "feature"

    # Step 0: A conditional type's entrance is checked BEFORE any default is applied, so that
    # no path exists on which the discount is granted and then withdrawn. Raising here also
    # means the refusal cannot be mistaken for a gate result: the change is not verified under
    # a lane it does not have, which is the point of refusing instead of substituting.
    if change_type in CONDITIONAL_CHANGE_TYPES:
        from .change_type_lanes import require_exit_obligation
        require_exit_obligation(change_type, tree, profile)

    # Step 1: Start with universal gates all "run"
    gates: dict[str, str] = {
        "build": "run", "test": "run", "scope_check": "run",
        "test_files": "run", "review": "run", "rules": "run",
        "spec_verify": "run",
    }

    # Step 2: Apply universal change_type defaults.
    #
    # An UNRECOGNISED change_type is not an error and must not be: a project may name its
    # own, and the all-"run" baseline above is the strictest set, so the fail direction is
    # closed. But it was also SILENT, which is the diagnosable half of the same problem —
    # a typo (`infrastructur`) and a deliberate new lane are indistinguishable from the
    # operator's chair, and the operator sees gates they never configured.
    #
    # It does NOT fall back to `feature`'s set, which is the natural assumption and is
    # wrong in a load-bearing way: `feature` softens `rules` to "warn", while an unknown
    # type keeps it blocking. Measured, after a peer inferred the fallback from the
    # `or "feature"` on the line above — that default only covers an ABSENT or empty value.
    if change_type not in UNIVERSAL_DEFAULTS:
        logger.warning(
            "gate config: change_type %r is not one of %s — no per-type defaults apply, so "
            "every universal gate stays blocking (this is stricter than 'feature', which "
            "softens 'rules'). If this is a typo the gates will look unexplained; if it is "
            "a deliberate lane, add it to UNIVERSAL_DEFAULTS.",
            change_type, sorted(UNIVERSAL_DEFAULTS),
        )
    gates.update(UNIVERSAL_DEFAULTS.get(change_type, {}))

    # Non-gate attrs from change_type
    type_attrs = _CHANGE_TYPE_ATTRS.get(change_type, {})

    # Step 3: Add profile-registered gate defaults
    if profile is not None and hasattr(profile, "register_gates"):
        try:
            for gd in profile.register_gates():
                if gd.phase != "pre-merge":
                    continue
                gates[gd.name] = gd.defaults.get(change_type, "run")
        except Exception:
            logger.warning("Failed to load profile gates", exc_info=True)

    # Step 4: Profile gate_overrides()
    if profile is not None and hasattr(profile, "gate_overrides"):
        overrides = profile.gate_overrides(change_type)
        if overrides:
            for key, val in overrides.items():
                if key in ("test_files_required", "max_retries", "review_model", "review_extra_retries"):
                    type_attrs[key] = val
                else:
                    gates[key] = val

    config = GateConfig(gates=gates, **type_attrs)

    # Step 5: Per-change explicit overrides
    if getattr(change, "skip_test", False):
        config.set("test", "skip")
        config.test_files_required = False
    if getattr(change, "skip_review", False):
        config.set("review", "skip")

    gate_hints = getattr(change, "gate_hints", None) or {}
    for key, val in gate_hints.items():
        if key in ("test_files_required", "max_retries", "review_model", "review_extra_retries"):
            setattr(config, key, val)
        else:
            config.set(key, val)

    # Step 6: Directive overrides (nested dict: {change_type: {gate: mode}})
    if directives:
        gate_overrides_dict = directives.get("gate_overrides", {})
        if isinstance(gate_overrides_dict, dict):
            type_overrides = gate_overrides_dict.get(change_type, {})
            if isinstance(type_overrides, dict):
                for key, val in type_overrides.items():
                    if key in ("test_files_required", "max_retries", "review_model", "review_extra_retries"):
                        setattr(config, key, val)
                    else:
                        config.set(key, val)

    # Step 7: Content-aware augmentation (section 7 of
    # fix-replan-stuck-gate-and-decomposer). Purely additive — the
    # classifier UNIONs gate names derived from `change.touched_file_globs`
    # into the current gate set. Never removes. `gate_hints="require"`
    # wins; `gate_hints="skip"` wins over classifier suggestions.
    try:
        from .gate_registry import augment_gate_config_with_content
        augment_gate_config_with_content(config, change, profile)
    except Exception:
        logger.debug("content-aware gate augmentation skipped", exc_info=True)

    change_name = getattr(change, "name", "?")
    logger.debug(
        "Gate config for %s (type=%s): %s",
        change_name, change_type,
        {k: v for k, v in sorted(config._gates.items())},
    )
    return config
