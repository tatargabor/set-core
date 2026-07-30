"""The project's map from its own lane signals onto set-core's change types.

Layer 1, and holding no mapping of its own. A change type resolves a whole gate chain from a
self-declared word (`gate_profiles.py`), and one of those words — `bugfix` — buys a cheaper
entrance. What pays for it is an *enforced exit obligation*: a lane signal of the project's
own, blocking, that fires when a fixed defect can silently return. Only the project holds both
halves of that sentence, so only the project can write the mapping down.

**Why the obvious implementation is refused rather than merely unused.** `LaneSignal.lane` is a
project-side label, and comparing it to a change type is one line of code that works perfectly
for any project whose lanes happen to be called `bugfix` and `feature`. That coincidence is the
worst available reason to build the coupling: a project whose lanes are called `restoring` and
`changing` would have to rename them to set-core's words, which is the design failing rather
than the project. `test_nothing_compares_a_lane_label_to_a_change_type` exists because this is
the implementation a later reader reaches for, and it looks like a simplification.

**Refuse, never default — and here the direction is unusually sharp.** An absent mapping means
"no exit obligation", which is already the refusal path for a conditional type. So a typo in the
mapping cannot be treated as absence: it would present as a project that declared nothing, the
refusal message would name the wrong cause, and the fix would be invisible. Every key that is
not a change type is therefore refused outright — not just the near misses. The key space is
closed (the six-or-so names in `UNIVERSAL_DEFAULTS`), so an unrecognised key can never do
anything, and a declaration that can never do anything must not read as a declaration.

**What this module logs.** Shape, never content — signal names, change types a project chose to
map, and its file layout are the project's own material. Same rule as `lane_signals`: the
framework's logger gets counts and reasons, the actionable detail rides on the refusal object
and reaches the developer through the gate's own output.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

# Imported rather than re-implemented, deliberately: a second copy of the key normaliser is
# precisely the defect the first half of this change removed. If it ever needs to be shared
# more widely it gets promoted, not duplicated.
from .lane_signals import _normalise_key

logger = logging.getLogger(__name__)

#: Where a project declares the mapping, relative to the tree. One file, one shape, one fact —
#: the alternative considered and rejected was a per-signal field naming the change type it
#: gates, which puts one fact in N places.
MAP_FILENAME = Path("set") / "change-type-lanes.json"


class LaneMapRefused(Exception):
    """A mapping declaration was rejected. Carries the key and the reason.

    Raised per key and collected, not per file: one bad key must not discard the others, for
    the same reason `SignalRefused` is per signal — a refusal that silences the whole
    declaration converts a typo into an unguarded run that looks exactly like a guarded one.
    """

    def __init__(self, key: str, reason: str, detail: str = ""):
        self.key = key
        self.reason = reason
        self.detail = detail
        super().__init__(f"change-type lane map key {key!r} refused: {reason}"
                         + (f" ({detail})" if detail else ""))


@dataclass
class LaneMapReadResult:
    """The mapping that survived, and the refusals — side by side, never in place of each
    other. A refusal nobody sees is how a project ends up believing a lane is mapped."""

    mapping: dict = field(default_factory=dict)
    refusals: list = field(default_factory=list)

    @property
    def declared_nothing(self) -> bool:
        """True only when the project declared no mapping AT ALL.

        Distinct from "every key was refused", which is the case a caller must be able to
        name: reporting "no exit obligation declared" for a project that declared one and
        mistyped it puts the blame on the wrong half of the sentence.
        """
        return not self.mapping and not self.refusals


def _parse_mapping(raw: Any, known_types: tuple, source: Optional[str],
                   result: LaneMapReadResult) -> None:
    """Validate one declaration block into `result`, refusing per key."""
    if not isinstance(raw, dict):
        result.refusals.append(LaneMapRefused(
            "<file>", "declaration is not a mapping", type(raw).__name__))
        return

    normalised_known = {_normalise_key(t): t for t in known_types}

    for key, value in raw.items():
        if key not in known_types:
            # A near miss is named when one is detectable, because the message is the whole
            # value of the refusal — but the refusal does NOT depend on finding one. An
            # unrecognised key in a closed key space can never resolve anything, and a
            # declaration that can never resolve anything must not read as a declaration.
            candidate = _normalise_key(key)
            # EVERY resembling type, not the first one found. `next(...)` here would be a
            # silent tie-break inside the only thing this refusal produces — its message — and
            # a truncated key like `cleanup` genuinely resembles two real types. Naming one of
            # them sends the reader to fix the wrong end; the same class as `replace(x, y, 1)`
            # and `head -1`, which this repo's rule book refuses on the grounds that a
            # tie-break inside a measurement is a guess wearing a result's clothes.
            resembles = [field_name for norm, field_name in normalised_known.items()
                         if norm in candidate or candidate in norm]
            detail = (
                f"{key!r} is not a change type; it looks like "
                f"{' or '.join(repr(r) for r in resembles)} — if that is what it was meant to "
                f"be, this reader never saw it and the change would have been refused for "
                f"having NO exit obligation, which names the wrong cause"
                if resembles else
                f"{key!r} is not a change type. Valid: {', '.join(known_types)}"
            )
            result.refusals.append(LaneMapRefused(key, "not a change type", detail))
            continue

        # A string is the likely shape for one signal and would iterate per character —
        # silently producing a list of one-letter signal names that match nothing. That is
        # the same reassuring direction as a missing key, so it is accepted and normalised
        # rather than refused: the project meant one signal.
        if isinstance(value, str):
            names: tuple = (value,)
        elif isinstance(value, (list, tuple)):
            names = tuple(value)
        else:
            result.refusals.append(LaneMapRefused(
                key, "mapped value is neither a signal name nor a list of them",
                type(value).__name__))
            continue

        bad = [n for n in names if not isinstance(n, str) or not n.strip()]
        if bad or not names:
            result.refusals.append(LaneMapRefused(
                key, "mapped value names no usable signal",
                "an empty list is not 'no obligation' — it is a declaration that says nothing, "
                "and the two must not be spelled the same way"))
            continue

        result.mapping.setdefault(key, [])
        for name in names:
            if name not in result.mapping[key]:
                result.mapping[key].append(name)

    logger.debug("change-type lane map: %d key(s) accepted, %d refused (source=%s)",
                 len(result.mapping), len(result.refusals), "profile" if source is None else "tree")


def read_lane_map(tree: Any, profile: Any = None) -> LaneMapReadResult:
    """Read the project's change-type → lane-signal mapping FROM THE TREE.

    Never invokes a status-contract command, an HTTP endpoint or a database — the same
    constraint `read_declarations` obeys and for the same reason: this is read while verifying
    a worktree, where no live project exists to ask, and a declaration reachable only through
    a running system is unreadable exactly when it is needed. Its absence would then read as
    "nothing to check", which is the direction that costs.

    Resolution order mirrors the signal reader: the profile's own declaration first (a project
    type may supply one), then the file in the tree.
    """
    from .gate_profiles import valid_change_types

    known = valid_change_types()
    result = LaneMapReadResult()

    supplier = getattr(profile, "change_type_lanes", None) if profile is not None else None
    if callable(supplier):
        try:
            declared = supplier() or {}
            if declared:
                _parse_mapping(declared, known, None, result)
        except Exception as exc:  # a broken profile must not take the tree's mapping down
            logger.warning("profile.change_type_lanes() raised %s", type(exc).__name__)
            result.refusals.append(LaneMapRefused(
                "<profile>", "profile supplier raised", f"{type(exc).__name__}: {exc}"))

    path = Path(tree) / MAP_FILENAME
    if path.is_file():
        try:
            _parse_mapping(json.loads(path.read_text()), known, str(path), result)
        except (OSError, ValueError) as exc:
            logger.warning("change-type lane map unreadable: %s", type(exc).__name__)
            result.refusals.append(LaneMapRefused(
                "<file>", "declaration file unreadable", f"{path}: {exc}"))

    if result.declared_nothing:
        logger.debug("no change-type lane map in this tree")
    return result


# ── The entry condition ─────────────────────────────────────────────


class ConditionalLaneRefused(Exception):
    """A conditional change type was declared and its entry condition is unmet.

    Raised rather than absorbed, and the reason is belief rather than danger. Falling back to
    another type's profile is *stricter*, so nothing breaks — but the project declared a lane,
    would believe it has one, and would silently run an ordinary change. A false belief is what
    carries a wrong decision later, which is the marker-true-of-a-narrower-subject class.

    `reason_class` exists so a caller can tell the cases apart without reading the sentence:
    merged, a project that has not yet earned its promotion reads identically to one that
    declared nothing, and those two need opposite next actions.
    """

    #: A project declared no mapping for this type at all.
    NO_MAPPING = "no-mapping"
    #: A mapping exists but every key of it was refused.
    MAP_REFUSED = "map-refused"
    #: The mapping names a signal the project does not declare.
    UNKNOWN_SIGNAL = "unknown-signal"
    #: The mapped signal is declared but still evaluates at WARN.
    NOT_ENFORCED = "not-enforced"
    #: No tree was supplied, so the obligation could not be read at all.
    NO_TREE = "no-tree"

    def __init__(self, change_type: str, reason_class: str, message: str):
        self.change_type = change_type
        self.reason_class = reason_class
        super().__init__(message)


def require_exit_obligation(change_type: str, tree: Any, profile: Any = None) -> str:
    """Return the mapped signal that pays for `change_type`'s cheaper entrance, or refuse.

    "Enforced" means the signal BLOCKS, not that it exists. A WARN-severity signal leaves the
    discount unpaid — the entrance gets cheaper and nothing stops the defect returning — and
    lane signals reach ENFORCE only once the project's own declared measurement is recorded.
    So a project cannot obtain the discount on day one: it runs the signal at WARN, earns the
    promotion, and only then does the entrance change. **That ordering is the requirement, not
    a side effect: the evidence is the price, so it cannot be paid afterwards.**
    """
    from .lane_evaluator import ENFORCE, resolve_severity
    from .lane_signals import read_declarations

    if tree is None:
        raise ConditionalLaneRefused(
            change_type, ConditionalLaneRefused.NO_TREE,
            f"change_type {change_type!r} carries an entry condition, but no worktree was "
            f"supplied so the project's exit obligation could not be read. Refused rather "
            f"than granted: an unreadable obligation is not a satisfied one.")

    read = read_lane_map(tree, profile=profile)
    mapped = read.mapping.get(change_type) or []

    if not mapped:
        if read.refusals:
            raise ConditionalLaneRefused(
                change_type, ConditionalLaneRefused.MAP_REFUSED,
                f"change_type {change_type!r} needs an enforced exit obligation. A mapping was "
                f"declared and every applicable key was refused, so this is NOT a project that "
                f"declared nothing — fix the declaration:\n  " +
                "\n  ".join(str(r) for r in read.refusals))
        raise ConditionalLaneRefused(
            change_type, ConditionalLaneRefused.NO_MAPPING,
            f"change_type {change_type!r} buys a cheaper entrance and is refused without an "
            f"enforced exit obligation. This project declares no lane signal for it in "
            f"{MAP_FILENAME}. Nothing is substituted: a change declaring no conditional type "
            f"keeps today's behaviour, which is already the strictest chain, so nothing is "
            f"lost by not asking for the discount.")

    declarations = read_declarations(tree, profile=profile)
    by_name = {s.name: s for s in declarations.signals}
    promotions = (getattr(profile, "lane_promotions", lambda: {})()
                  if callable(getattr(profile, "lane_promotions", None)) else {})

    unknown: list = []
    unpromoted: list = []
    for name in mapped:
        signal = by_name.get(name)
        if signal is None:
            unknown.append(name)
            continue
        severity, refusal = resolve_severity(signal, promotions)
        if severity == ENFORCE:
            logger.info("conditional lane granted: exit obligation is enforced")
            return name
        unpromoted.append((name, refusal))

    if unpromoted:
        detail = "; ".join(
            f"{name} is declared but evaluates at WARN"
            + (f" — {refusal}" if refusal else
               " (its own promotion does not ask for enforce)")
            for name, refusal in unpromoted)
        raise ConditionalLaneRefused(
            change_type, ConditionalLaneRefused.NOT_ENFORCED,
            f"change_type {change_type!r} is mapped to an exit obligation that does not block "
            f"yet: {detail}. This is NOT an absent mapping — the promotion has not been earned. "
            f"Record the measurement the signal's own promotion condition names, then declare "
            f"the type.")

    raise ConditionalLaneRefused(
        change_type, ConditionalLaneRefused.UNKNOWN_SIGNAL,
        f"change_type {change_type!r} is mapped to signal(s) {', '.join(unknown)} which this "
        f"project does not declare"
        + (f"; {len(declarations.refusals)} signal declaration(s) were refused, which may be "
           f"why" if declarations.refusals else "") +
        ". A mapping naming a signal that does not exist is not an obligation.")
