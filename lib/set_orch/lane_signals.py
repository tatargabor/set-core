"""Lane signal declarations — the reader half of lane-contradiction detection.

Layer 1, and deliberately empty of content. set-core resolves a change's whole gate
chain from a self-declared `change_type` (`gate_profiles.py`), and nothing checks that
declaration afterwards. A lane signal is a project's own narrow, mechanically-decidable
condition, evaluated AFTER the work, that fires when the delivered artefacts contradict
the declared lane.

This module reads those declarations and refuses malformed ones. It contains no signal,
no path pattern and no defect-store name of its own — those are project data, exactly as
contract commands are. A signal shipped with the framework works for whoever it was
written against and silently mismeasures everyone else, while looking authoritative to
both.

Three refusals are worth their strictness, because each has a defaulting failure that is
invisible:

- **no scope** — a defaulted scope judges work its author never meant it to;
- **no baseline** — a defaulted baseline forgives the existing backlog silently;
- **no promotion condition** — a warning becomes a blocker with nobody deciding.

And two that come from measured incidents rather than reasoning:

- **a volume condition** (lines/files changed) is refused outright. A large generated
  update is routine while a small change to a decision predicate on a critical path is
  not, so a size threshold fires hardest on the safest population — worse than not firing,
  because it teaches everyone to ignore it.
- **a scope that includes the signal's own definition** is refused. A pattern-based signal
  matches the sentence describing the pattern, so the gate reports its own rule as a
  violation, and the cheapest way to silence it is to delete the explanation.

**What is machine-checked, stated because the first draft blurred it:** the triggering
case's date and identifier are checked here; whether the accompanying text actually
explains anything is NOT, and this module never claims it does. Whether a paragraph
explains something is not mechanically decidable — two independent proxies for it were
tried elsewhere and both misclassified, in opposite directions. A declaration carrying
only a date is accepted and reported as unexplained, so review has something to act on
rather than a silent pass.

**What this module logs, and why it says so little.** A declaration is a project's own
material: its path conventions, its defect-store location, its signal names. The framework
may READ all of that and must persist none of it — and a log is a persistence carrier that
crosses machines without anyone deciding it should. So the framework's own logger gets the
SHAPE (how many signals, how many refused, which reason, how many condition keys) and never
the values. The actionable detail — which key matched, which pattern, which path — is
carried by the `SignalRefused` object and printed in the gate's output, which is the
project's own report about its own tree. Same rule as `db_safety.py` logging a URL's scheme
and nothing else.

See `openspec/changes/lane-contradiction-detection/` for the requirements this implements.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

from .project_status import is_valid_command_name

logger = logging.getLogger(__name__)

#: The six fields a declaration must carry. Absence of any one is a refusal, never a
#: default — see the module docstring for why each default would be invisible.
REQUIRED_FIELDS = ("lane", "condition", "scope", "baseline", "promotion", "triggering_case")

#: Fields where an empty value is a real declaration rather than an omission. Only the
#: baseline: "this signal starts with no outstanding debt" is a statement, whereas an empty
#: lane or scope says nothing and must still be refused.
EMPTY_IS_MEANINGFUL = frozenset({"baseline"})

#: Condition kinds known to measure volume. This list exists only to produce a clearer
#: error; it is NOT the test. A closed list of names is a narrowing, and a narrowing fails
#: in the reassuring direction — it accepts `loc_delta` because nobody thought of that word.
#: The test below is the SHAPE: a numeric threshold.
VOLUME_KINDS = frozenset({
    "lines_changed", "files_changed", "diff_size", "insertions", "deletions", "churn",
})

#: Keys that express "how much". A shape condition never needs one — it asks whether a
#: module appeared, whether a fixed defect cites a test. So a numeric value under any of
#: these is the mechanical signature of a volume condition, whatever the kind is called.
THRESHOLD_KEYS = frozenset({
    "over", "under", "min", "max", "minimum", "maximum", "threshold",
    "at_least", "at_most", "greater_than", "less_than", "count", "limit",
})

#: A date in the triggering case. Only the presence of a date and an identifier is
#: checked; see the module docstring on what is deliberately NOT checked.
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


class SignalRefused(Exception):
    """A declaration was rejected. Carries the field or rule that caused it.

    Raised per signal and caught by the reader: one bad declaration must not disable the
    others, because a refusal that silences a whole signal set converts a typo into an
    unguarded run that looks exactly like a guarded one.
    """

    def __init__(self, signal_name: str, reason: str, detail: str = ""):
        self.signal_name = signal_name
        self.reason = reason
        self.detail = detail
        super().__init__(f"lane signal {signal_name!r} refused: {reason}"
                         + (f" ({detail})" if detail else ""))


@dataclass(frozen=True)
class LaneSignal:
    """One project-declared signal. Every field comes from the project."""

    name: str

    #: **A project-side LABEL that the framework never interprets.** Nothing compares it to
    #: a change's `change_type`, and nothing should: the mapping between a project's lane
    #: vocabulary and set-core's change types is domain, and a built-in mapping would be
    #: exactly the content this layer refuses to hold. The contradiction is carried by the
    #: CONDITION firing while a cheap `change_type` was declared — the two names sitting
    #: near each other in the report is for the reader, not a machine check.
    #:
    #: Named as a limit because the field name promises more than it delivers, and the name
    #: is the copy that travels. Caught by the peer reading this code, not by its author.
    lane: str

    condition: dict
    scope: str
    baseline: tuple
    promotion: dict
    triggering_case: str
    exclusions: tuple = ()

    #: Declared keys this set-core version does not read, kept verbatim and NOT interpreted.
    #:
    #: Without this the reader silently discarded them, which is the false-absence class
    #: pointed inward: a project declares something, the framework keeps nothing, and
    #: nothing says so. It surfaced when a project attached a reference to the canonical
    #: implementation of its own condition — the whole point of which is that a handler and
    #: the project's own gate can be COMPARED, so discarding it removes the comparison that
    #: would have caught a divergence.
    #:
    #: Preserved as opaque data on purpose. Naming any of these keys in Layer 1 would make
    #: the framework hold project vocabulary, which is exactly what this module refuses;
    #: the gate reports that they exist, by key name, and interprets none of them.
    #: An optional delegation: the project already publishes this answer, so the gate asks
    #: rather than recomputing. `{command, field}` — set-core defines the shape, the project
    #: supplies the value. See `_parse_answer` for why a malformed one is refused.
    answer: Optional[dict] = None

    #: The project's own statement that NO other gate enforces this signal's defect class.
    #:
    #: Default False, and the default is the honest one: a peer accepted framework silence
    #: on an unevaluable signal *because their own blocking gate covered the same class*, so
    #: silence there costs earlier warning rather than protection. Where that is not true,
    #: silence is a real hole — so a project may say so, and an unevaluable signal then
    #: BLOCKS instead of reporting quiet. Opt-in on purpose: a framework that guessed this
    #: would either block every clone or forgive every hole.
    sole_enforcement: bool = False

    extra: dict = field(default_factory=dict)

    @property
    def is_explained(self) -> bool:
        """Whether the triggering case carries anything beyond a date and an identifier.

        NOT a judgement about quality — see the module docstring. It exists so the gate
        can REPORT an unexplained signal instead of passing it silently, which is review's
        cue rather than the machine's verdict.
        """
        without_date = _DATE.sub("", self.triggering_case)
        return len(without_date.split()) > 2


@dataclass
class DeclarationReadResult:
    """Signals that survived, and the refusals — reported side by side, never in place
    of each other. A refusal list nobody sees is how a project ends up believing it is
    guarded by a signal that never loaded."""

    signals: list = field(default_factory=list)
    refusals: list = field(default_factory=list)

    @property
    def declared_nothing(self) -> bool:
        """True only when the project declared no signals AT ALL.

        Distinct from "every signal was refused" and from "all signals passed" — the
        caller must be able to tell an absent declaration from a clean run, because
        reporting an all-clear for a project that declared nothing is a false absence in
        the one place it would be believed.
        """
        return not self.signals and not self.refusals


def walk_leaves(value: Any, path: str = "") -> Iterable[tuple]:
    """Yield `(key_path, key, leaf)` for every scalar inside nested dicts/lists/tuples.

    Exists because both condition rules were **narrowed by traversal depth** — they walked
    `condition.items()` once and stopped. That is the same class as a closed list of key
    names, one level down, and it failed the same reassuring way. Measured by the peer and
    reproduced here: of six disguises, one was refused and five walked through —
    `{"globs": ["set/*.json"]}`, `{"where": {"glob": ...}}`, `{"limits": [{"over": 500}]}`,
    `{"where": {"over": 500}}` and an arbitrarily nested variant.

    The list form is not exotic; it is the *likely* form. Anyone listing path patterns
    writes a list, so the probable shape was the evading shape.
    """
    if isinstance(value, dict):
        for key, sub in value.items():
            yield from walk_leaves(sub, f"{path}.{key}" if path else str(key))
    elif isinstance(value, (list, tuple)):
        for index, sub in enumerate(value):
            yield from walk_leaves(sub, f"{path}[{index}]")
    else:
        key = path.rsplit(".", 1)[-1].split("[", 1)[0]
        yield (path, key, value)


def _refuse_if_volume(name: str, condition: dict) -> None:
    """Refuse a condition that measures how much rather than what shape.

    Two checks, and the ORDER of their importance is the opposite of the order they were
    written in. The kind list is a convenience for a clearer message. The load-bearing
    check is the numeric threshold, because a closed list of names is a **narrowing**, and
    a narrowing fails in the reassuring direction: it accepted `loc_delta` and `hunk_count`
    while the commit introducing it claimed a project "cannot smuggle one past by
    expressing the threshold differently". Measured — three of four disguises passed.

    **And then the fix itself was narrowed, by depth.** It walked one level, so
    `{"limits": [{"over": 500}]}` and `{"where": {"over": 500}}` were accepted. The rule now
    runs on every leaf, at any nesting — see `walk_leaves`. Two rounds, same class, twice in
    the reassuring direction: worth stating that *a fix for a narrowing is itself a candidate
    narrowing until its own traversal is checked*.
    """
    kind = str(condition.get("kind", ""))
    if kind in VOLUME_KINDS:
        raise SignalRefused(
            name, "condition measures volume",
            f"kind={kind!r}; declare a SHAPE (a new module, a fixed defect with no test "
            f"citing its id), not a quantity",
        )

    numeric = sorted(
        key_path for key_path, key, leaf in walk_leaves(condition)
        if key in THRESHOLD_KEYS and isinstance(leaf, (int, float))
        and not isinstance(leaf, bool)
    )
    if numeric:
        raise SignalRefused(
            name, "condition measures volume",
            f"numeric threshold(s) at {numeric} under kind={kind!r}; a shape condition needs "
            f"no quantity, and a size threshold fires hardest on the safest population",
        )


def _matches(path: str, pattern: Any) -> bool:
    """Glob-match, tolerating the non-patterns a condition legitimately contains.

    A condition's values are a project's own vocabulary — kind names, store paths, flags —
    so most of them are not patterns at all. Anything unmatchable is simply not a match.
    """
    if not isinstance(pattern, str) or not pattern:
        return False
    try:
        return Path(path).match(pattern)
    except (ValueError, TypeError):
        return False


def _refuse_if_self_inclusive(name: str, condition: dict, scope: str,
                              exclusions: Iterable[str],
                              declared_at: Optional[str]) -> None:
    """Refuse a signal whose own CONDITION would select the document declaring it.

    Checked against the declaration's own path rather than against a guessed set of
    "documentation" paths: the framework does not know which files a project treats as
    its rule book, and guessing would be a built-in pattern of exactly the kind this
    module refuses to hold.

    **Checked against the condition, not only the scope — and that correction matters more
    than it looks.** The first implementation matched `declared_at` against `scope` alone.
    But `scope` is the PHASE a signal runs in (`per-change-verification`), which the
    evaluator compares by equality; a phase name glob-matches no path, so the refusal could
    never fire on a well-formed declaration. It could only fire on one whose scope was a
    path glob — which is a *different* defect, and one that leaves the signal permanently
    unevaluated anyway. A guard that cannot fire on any legitimate input is a false gate:
    it reads as protection, is cited as protection, and protects nothing. Measured, not
    reasoned — a condition patterned `set/*.json` declared in `set/lane-signals.json` was
    accepted.

    Every string in the condition is tested, not a chosen key name: a closed list of keys
    (`pattern`, `glob`, `paths`) is a narrowing, and narrowings fail in the reassuring
    direction. **At any nesting depth**, for the same reason one level down — a list of
    globs is the *likely* way to write several path patterns, and it was walking straight
    through. See `walk_leaves`.
    """
    if not declared_at:
        return
    excl = tuple(exclusions or ())
    if any(_matches(declared_at, pattern) for pattern in excl):
        return

    for key_path, _key, leaf in walk_leaves(condition):
        if _matches(declared_at, leaf):
            raise SignalRefused(
                name, "the condition selects the declaration itself",
                f"{declared_at} matches condition.{key_path}={leaf!r} and no exclusion "
                f"covers it; a signal that reports its own definition gets silenced by "
                f"deleting the explanation",
            )

    if _matches(declared_at, scope):
        raise SignalRefused(
            name, "scope includes the declaration itself",
            f"{declared_at} matches scope {scope!r} and no exclusion covers it; a signal "
            f"that reports its own definition gets silenced by deleting the explanation",
        )


#: The keys of an `answer` declaration. set-core defines this SHAPE; the project fills it
#: in — which is the whole agreement in one line: the framework says what a delegation looks
#: like, the project says which of its commands answers and which field carries the value.
ANSWER_FIELDS = ("command", "field")


def _parse_answer(name: str, raw: Any) -> Optional[dict]:
    """Validate an optional delegation declaration.

    A signal may name an answer the project ALREADY publishes through its status contract,
    instead of describing a rule for set-core to reimplement. Two implementations of one
    business value diverge silently — measured on a consumer before this existed, where the
    same figure reached 412% down one path and 164% down another, and a customer noticed
    before either team did.

    Absent is legitimate and common: a condition the framework evaluates itself needs no
    delegation. But a MALFORMED one is refused rather than ignored, because ignoring it
    would silently fall back to "no delegation" — and the fallback is precisely the
    reimplementation the field exists to prevent.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise SignalRefused(name, "answer is not a mapping", type(raw).__name__)

    missing = [f for f in ANSWER_FIELDS if not raw.get(f) or not isinstance(raw[f], str)]
    if missing:
        raise SignalRefused(
            name, "answer is missing required field(s)", ", ".join(missing) +
            "; an answer names the command that already publishes the value and the field "
            "that carries it",
        )
    if not is_valid_command_name(raw["command"]):
        raise SignalRefused(
            name, "answer names an invalid command",
            "a command name reaching a shell unvalidated is the hole the status contract "
            "already closed; the same rule applies here",
        )

    # `field` is a dotted path of PLAIN KEYS, resolved against the envelope's `data`. No
    # index, no projection, no filter — and the restriction is the whole point rather than
    # a parser limitation. A projection like `bugs[?fixed && !hasTest]` is the project's
    # RULE re-expressed in the framework's syntax, which is the second implementation this
    # field exists to prevent; the 412%-vs-164% divergence it was written after did not need
    # two languages to happen, only two places. So the project publishes the already-decided
    # list under one path, and set-core reads it.
    bad = [seg for seg in raw["field"].split(".") if not seg or any(c in seg for c in "[]*?")]
    if bad:
        raise SignalRefused(
            name, "answer field is not a plain dotted path",
            f"{raw['field']!r} — an index or filter here would make set-core re-apply the "
            f"project's own rule, which is exactly the second implementation this "
            f"delegation exists to prevent; publish the decided list under one path instead",
        )
    return {f: raw[f] for f in ANSWER_FIELDS}


def _normalise_key(key: str) -> str:
    """Lowercase, letters and digits only — so `sole-enforcement` and `soleEnforcement`
    collapse onto the same string as the field they were aiming at."""
    return "".join(c for c in str(key).lower() if c.isalnum())


#: The fields whose ABSENCE is silent, and therefore the only ones a near-miss check is
#: worth its false positives for. Every required field is already protected by accident: a
#: typo there leaves the real field missing, which is refused with a message naming it. So
#: checking those too would add nothing but over-refusals — `lane` normalises to four
#: characters, and any project key containing `lane` (or `plane`) would collide.
#:
#: Derived from `LaneSignal`'s own optional fields by a test, not by hand, so that adding an
#: optional field without extending this tuple fails rather than silently reopening the hole.
SILENTLY_OPTIONAL_FIELDS = ("exclusions", "answer", "sole_enforcement")


def _refuse_near_miss_keys(name: str, extra: dict, known: Iterable[str]) -> None:
    """Refuse a declared key that was clearly aiming at a field this reader knows.

    Peer-raised, and they found it by MEASURING the miss rather than reasoning about it: a
    mistyped or renamed delegation key is not an error today — it lands in `extra`, the
    signal is built with `answer=None`, and evaluation quietly takes the handler route. That
    is the same reassuring direction `_parse_answer` refuses a MALFORMED answer for, arriving
    one step earlier: the fallback IS the second implementation, and a typo must not be able
    to select it. The key names that would do it are the project's vocabulary and are
    deliberately not written here — the check is a shape, not a list.

    The class is wider than `answer`, which is why this is not a list of three names.
    `sole_enforcement` has the same hole in the worse direction: a mistyped flag silently
    reads as False, so a signal its project declared the only enforcement of its class stops
    blocking, and nothing says so. The required six are deliberately NOT checked — a typo
    there leaves the real field missing, which is already refused by name, so including them
    would buy nothing and cost over-refusals on any key containing a short field name.

    A legitimate project key that merely resembles a framework field is refused too, and
    that is the intended trade: refusal is loud, cheap and fixed by renaming, whereas the
    silent version is a protection that reports nothing while doing nothing. Same reasoning
    as D4 — refuse, never default.

    `[NOT READ]` does not cover this. It is a report, not a gate; the project would still
    believe the framework acted on a field it merely stored.
    """
    normalised_known = {_normalise_key(k): k for k in known}
    for declared in extra:
        candidate = _normalise_key(declared)
        for norm, field_name in normalised_known.items():
            # Either direction: a prefixed key CONTAINS the field name, and a truncated one
            # is CONTAINED BY it. A near miss is a near miss whichever way the extra
            # characters fell.
            #
            # The escape clause compares the RAW key to the field name, never the normalised
            # forms. Comparing normalised forms let a pure case or separator variant through
            # — it normalises to the field name exactly, so an "is it different?" test on the
            # normalised string said no while the reader, which matches raw keys, had already
            # ignored it. Found by the test written next to this function, which is the point
            # of writing the shapes out rather than one happy-path example.
            if declared != field_name and (norm in candidate or candidate in norm):
                raise SignalRefused(
                    name, f"declared key {declared!r} looks like {field_name!r}",
                    f"if it was meant to be {field_name!r}, this reader never saw it and "
                    f"would have carried on as though the field were absent — for "
                    f"'answer' that silently selects the framework-side handler route, "
                    f"which is the recomputation the delegation exists to prevent. Rename "
                    f"it to {field_name!r}, or to something that cannot be read as it",
                )


def parse_signal(name: str, raw: dict, declared_at: Optional[str] = None) -> LaneSignal:
    """Validate one declaration. Raises `SignalRefused`; never returns a partial signal."""
    if not isinstance(raw, dict):
        raise SignalRefused(name, "declaration is not a mapping", type(raw).__name__)

    # Emptiness means different things per field, so "missing" is decided per field.
    #
    # An EMPTY BASELINE is the legitimate state of a signal introduced into a clean tree —
    # treating `[]` as missing refused exactly the project with no debt, which is the one
    # a new signal is easiest to adopt in. So for the collection field, presence of the key
    # is the test, keeping "declared zero debt" apart from "never thought about debt".
    #
    # An EMPTY LANE OR SCOPE means nothing at all, and relaxing those the same way would
    # let `""` through — a narrowing fix that opens a wider hole than it closes.
    missing = [f for f in REQUIRED_FIELDS
               if (raw.get(f) is None) or (f not in EMPTY_IS_MEANINGFUL and not raw.get(f))]
    if missing:
        raise SignalRefused(name, "missing required field(s)", ", ".join(missing))

    exclusions = raw.get("exclusions") or ()
    if not exclusions:
        raise SignalRefused(
            name, "missing required field(s)", "exclusions",
        )

    condition = raw["condition"]
    if not isinstance(condition, dict) or not condition.get("kind"):
        raise SignalRefused(name, "condition has no kind", repr(condition)[:80])
    _refuse_if_volume(name, condition)

    triggering = str(raw["triggering_case"])
    if not _DATE.search(triggering):
        raise SignalRefused(
            name, "triggering case carries no date",
            "a signal with no incident behind it is a guess dressed as a rule",
        )

    _refuse_if_self_inclusive(name, condition, str(raw["scope"]), exclusions, declared_at)

    answer = _parse_answer(name, raw.get("answer"))

    # A strict bool, never a truthiness test. `"false"` is a true string, and this flag
    # decides whether an unevaluable signal blocks — a defaulting error here fails in
    # whichever direction the typo happened to point, which is worse than either.
    sole = raw.get("sole_enforcement", False)
    if not isinstance(sole, bool):
        raise SignalRefused(
            name, "sole_enforcement is not a boolean", f"got {type(sole).__name__}; "
            f"this flag decides whether an unevaluable signal blocks, so a string that "
            f"merely looks false would silently enable blocking")

    # Everything the project declared that this version does not read is KEPT, never
    # dropped — see `LaneSignal.extra`. Derived from the field list rather than a second
    # hard-coded set of names, so a future field cannot be preserved and read at once.
    known = set(REQUIRED_FIELDS) | {"exclusions", "answer", "sole_enforcement"}
    extra = {k: v for k, v in raw.items() if k not in known}
    _refuse_near_miss_keys(name, extra, SILENTLY_OPTIONAL_FIELDS)

    signal = LaneSignal(
        name=name,
        lane=str(raw["lane"]),
        condition=condition,
        scope=str(raw["scope"]),
        baseline=tuple(raw["baseline"]),
        promotion=raw["promotion"],
        triggering_case=triggering,
        exclusions=tuple(exclusions),
        answer=answer,
        sole_enforcement=sole,
        extra=extra,
    )
    # Shape, not content — see "What this module logs" in the module docstring.
    logger.debug("lane signal accepted: %d condition key(s), explained=%s",
                 len(condition), signal.is_explained)
    return signal


def read_declarations(tree: Path, profile: Any = None) -> DeclarationReadResult:
    """Read a project's lane signal declarations FROM THE TREE.

    Never invokes a status-contract command, an HTTP endpoint or a database. Signals are
    evaluated while verifying a worktree, where no live project exists to ask — a
    declaration reachable only through a running system is unreadable exactly when it is
    needed, and it fails in the direction that reads as "nothing to check".

    Resolution order: the profile's own declarations (a project type may supply them),
    then `set/lane-signals.json` in the tree. Absent means absent: no signals, no
    all-clear.
    """
    result = DeclarationReadResult()

    raw_sets: list[tuple[dict, Optional[str]]] = []

    supplier = getattr(profile, "lane_signals", None) if profile is not None else None
    if callable(supplier):
        try:
            declared = supplier() or {}
            if declared:
                raw_sets.append((declared, None))
        except Exception as exc:  # a broken profile must not take the tree's signals down
            logger.warning("profile.lane_signals() raised %s: %s", type(exc).__name__, exc)

    path = Path(tree) / "set" / "lane-signals.json"
    if path.is_file():
        try:
            raw_sets.append((json.loads(path.read_text()), str(path)))
        except (OSError, ValueError) as exc:
            logger.warning("lane signal file unreadable: %s", type(exc).__name__)
            result.refusals.append(SignalRefused("<file>", "declaration file unreadable",
                                                 f"{path}: {exc}"))

    if not raw_sets:
        logger.debug("no lane signal declarations in this tree — evaluating none")
        return result

    for declared, declared_at in raw_sets:
        for name, raw in sorted(declared.items()):
            try:
                result.signals.append(parse_signal(name, raw, declared_at))
            except SignalRefused as refusal:
                # The REASON, never the detail: the detail quotes the project's own
                # patterns and store names, and it already reaches the developer through
                # the refusal object and the gate's output. See "What this module logs" in the module docstring.
                logger.warning("lane signal refused: %s", refusal.reason)
                result.refusals.append(refusal)

    logger.info("lane signals: %d accepted, %d refused",
                len(result.signals), len(result.refusals))
    return result
