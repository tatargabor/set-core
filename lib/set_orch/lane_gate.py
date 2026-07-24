"""The lane gate — wiring the reader and the evaluator into the existing pipeline.

Registered through `gate-registry` like any other gate, so it inherits observability and
per-change configuration for free rather than growing a parallel mechanism.

**What this gate exists for.** A change's whole gate chain is resolved from a self-declared
`change_type` (`gate_profiles.py:145`), and until now nothing checked that declaration
afterwards: `infrastructure` skips build, test, e2e and test-files and softens
spec-verification, `cleanup-after` also skips review and rules — and in an autonomous run
the declaration is written by an agent, for whom the cheaper answer is less work. This gate
measures, after the fact, whether the delivered artefacts contradict it.

**Four things it must never do**, each of which would be worse than not having it:

- **Report an all-clear for a project that declared no signals.** Absence is `skipped`,
  never `pass`. A pass here is a false absence in the one place a reader believes it.
- **Count an unevaluated signal as a passing one.** They are reported separately, by name
  and reason.
- **Emit a verdict about the lane being correct.** It can prove a contradiction; it cannot
  prove there is none, since a change wrong in a way no declared signal covers passes
  silently.
- **Call a model, or require a new field on the change definition.** Both would put the
  cost of this gate on every change, and both would make it another thing to get right in
  advance — which is the entrance classification this whole capability replaces.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Iterable, Optional

from .lane_evaluator import LaneReport, evaluate
from .lane_signals import LaneSignal, _matches, read_declarations

logger = logging.getLogger(__name__)

GATE_NAME = "lane"


class UnhandledConditionKind(Exception):
    """This set-core version has no handler for a declared condition kind.

    A distinct type because the alternative — returning the evaluator's `None` — collapses
    it into "the condition's input is absent", which points the reader at their own tree.
    The two unevaluable reasons are opposites: one says a file is missing, the other says
    the framework cannot read this kind and the tree is fine. Merged, they send someone
    looking for a file that is not missing.
    """

    reason_class = "no-handler"


class ProjectPublishesNothing(Exception):
    """The signal names a published answer, and this tree publishes no contract to ask.

    Kept apart from `PublishedAnswerUnusable` at a peer's request, with a measurement behind
    it: on their side the entire read contract — every declared command AND both signal
    declarations — existed on one machine and was absent from the remote branch, so a clone
    or a CI run does not get a *wrong* answer, it finds nothing to ask. Collapsed into the
    broken case, a project that simply does not publish would report identically to one whose
    command is failing, and the gate would look like it had found something.

    Neutral is not a pass. It is still UNEVALUATED — it just says which of the two it is.
    """

    reason_class = "not-published"


class PublishedAnswerUnusable(Exception):
    """The project publishes, and the answer did not arrive in a usable form.

    Never a fallback computation — the spec forbids one, because a framework-side answer to
    a question the project already answers is the second implementation the whole delegation
    exists to prevent.
    """

    reason_class = "unusable-answer"


#: Error classes that mean *this tree does not publish*, as opposed to *it published badly*.
#: Read off `project_status.query`: `not-configured` is returned when no manifest and no
#: config key exist, `command-not-found` when the interpreter or script named by the contract
#: is not on disk. Both are the shape of a checkout that does not carry the publishing half —
#: the case measured on a peer's remote branch.
NOT_PUBLISHING = frozenset({"not-configured", "command-not-found"})

#: Sentinel for "this path is not in the answer", distinct from a published `None`.
_MISSING = object()


def _dig(data: Any, dotted: str) -> Any:
    """Walk a dotted path of plain keys. No index, no filter — see `_parse_answer`."""
    current = data
    for segment in dotted.split("."):
        if not isinstance(current, dict) or segment not in current:
            return _MISSING
        current = current[segment]
    return current


def _delegated_violations(signal: LaneSignal, wt_path: str) -> list:
    """Take the project's published answer. Never recompute it.

    This is the whole agreement in one function: set-core defines the SHAPE of a signal, the
    project supplies the VALUE. The alternative was measured on the consumer's side before
    this was written — two paths computing one business figure drifted to 412% and 164%, and
    a customer noticed before either team did. A framework-side reimplementation of a
    project's rule is that same defect with a longer feedback loop, because the two answers
    are read by different people.

    Safe against a live system only because the thing being asked is the WORKTREE: measured
    on a consumer's disposable tree with no `node_modules`, no `.env` and no database, their
    query answered in 129 ms and answered about *that tree*.
    """
    from . import project_status

    config = project_status.resolve_status_config(wt_path)
    if config is None:
        raise ProjectPublishesNothing(
            "this tree publishes no status contract, so the answer this signal delegates to "
            "cannot be asked for. That is not a finding about the change — it says the "
            "checkout does not carry the publishing half")

    command = signal.answer["command"]

    # A lane signal reads; it never writes. Checked here rather than trusted to the
    # declaration, because the declaration is the project's and this guarantee is the
    # framework's — and a gate that mutated the tree it is judging would be the worst
    # possible place to discover the distinction.
    if command in config.write_commands:
        raise PublishedAnswerUnusable(
            "the answer names a WRITE command; a lane signal reads and never mutates, so "
            "it was not invoked")
    if config.commands and command not in config.commands:
        raise PublishedAnswerUnusable(
            "the answer names a command this tree's contract does not declare as readable "
            "— two of the project's own declarations disagree, and guessing which one is "
            "current is not the framework's call")

    result = project_status.query(wt_path, command, config=config)
    if not result.ok:
        # Shape, not content: the class is the framework's vocabulary, the message is the
        # project's own and reaches the developer through the gate output.
        if result.error_class in NOT_PUBLISHING:
            raise ProjectPublishesNothing(
                f"the published command could not be reached ({result.error_class})")
        raise PublishedAnswerUnusable(
            f"the published answer did not arrive ({result.error_class}); no framework-side "
            f"computation was substituted, because a substitute is the second "
            f"implementation this delegation exists to prevent")

    value = _dig(result.data, signal.answer["field"])
    if value is _MISSING:
        raise PublishedAnswerUnusable(
            f"the answer arrived but carries nothing at the declared path "
            f"{signal.answer['field']!r} (resolved against the envelope's `data`)")
    if not isinstance(value, list):
        raise PublishedAnswerUnusable(
            f"the declared path holds {type(value).__name__}, not a list of violations. A "
            f"count cannot be baselined and cannot be excluded, so it would report a number "
            f"nobody can act on or forgive")

    violations = []
    for entry in value:
        if isinstance(entry, (dict, list, tuple, set)):
            raise PublishedAnswerUnusable(
                "a violation must be a stable identifier — the baseline and the exclusions "
                "both match on it, so a structured entry silently escapes both")
        violations.append(str(entry))
    return violations


def _detector_for(wt_path: str) -> Callable[[LaneSignal], Optional[list]]:
    """Return a detector that runs a signal's condition against the worktree.

    Layer 1 knows how to READ a condition, never what any particular condition means for a
    given project's layout — so an unrecognised kind is never an empty list. That direction
    matters: an empty list would make every unknown condition look like a clean result.

    **Exclusions are applied HERE, by the framework, not left to each handler.** The reason
    is a waiver: `lane_signals._refuse_if_self_inclusive` stops refusing a self-selecting
    condition as soon as an exclusion covers the declaration file. That waiver is only
    honest if the exclusion is guaranteed to take effect — otherwise a signal buys its way
    past the guard with a promise nothing enforces, and a per-handler implementation is
    exactly the kind of promise that holds until the second handler is written.

    Raised by an integration peer, who found the mirror of it on their own side: listing
    their declaration file in `exclusions` short-circuited the whole guard for that signal.
    **An escape hatch that disables the protection of the same signal it belongs to looks
    like care from the outside** — which is what makes it worth enforcing centrally.
    """

    def detect(signal: LaneSignal) -> Optional[list]:
        # Delegation is tried BEFORE any handler, and the order is a requirement rather than
        # a preference: where the project publishes the answer, a framework handler running
        # instead of it IS the recomputation the spec forbids. So a declared `answer` wins
        # even if this version happens to have a handler for the same condition kind.
        if signal.answer:
            return _apply_exclusions(signal, _delegated_violations(signal, wt_path))

        handler = _KIND_HANDLERS.get(str(signal.condition.get("kind", "")))
        if handler is None:
            # Shape, not content: the kind and the signal name are the project's own
            # vocabulary. They reach the developer through the gate's output, which is the
            # project's report about its own tree — see `lane_signals`' module docstring.
            logger.debug("lane signal: no handler for its condition kind — unevaluated")
            raise UnhandledConditionKind(
                "no handler for this condition kind in this set-core version; the tree is "
                "not at fault. A handler is added once a project declares a signal that "
                "needs it — until then the signal is unevaluated, never a pass"
            )
        found = handler(signal, wt_path)
        if found is None:  # "could not decide" survives untouched
            return None
        return _apply_exclusions(signal, found)

    return detect


def _apply_exclusions(signal: LaneSignal, found: Iterable) -> list:
    """Drop violations covered by the signal's own exclusions.

    A violation is usually a path, but a handler may return an id. Only path-shaped strings
    can match a glob, so anything else passes through untouched rather than being silently
    dropped — dropping an unrecognised shape would be the reassuring direction again.
    """
    # Materialised once: `found` may be a generator, and consuming it twice would silently
    # return an empty list — a false absence produced by the code that exists to prevent
    # them.
    all_found = list(found)
    kept = [v for v in all_found
            if not any(_matches(str(v), pattern) for pattern in signal.exclusions)]
    if len(kept) != len(all_found):
        logger.debug("lane signal: %d violation(s) removed by declared exclusions",
                     len(all_found) - len(kept))
    return kept


#: Condition kinds this layer can evaluate. Empty by design in this commit: the handlers
#: are mechanisms, and each one is only worth adding once a project declares a signal that
#: needs it. An unhandled kind is reported as unevaluated rather than silently passing.
_KIND_HANDLERS: dict = {}


def build_report(wt_path: str, change: Any = None, profile: Any = None,
                 phase: str = "per-change-verification") -> LaneReport:
    """Read declarations from the tree and evaluate them. No service is contacted."""
    read = read_declarations(wt_path, profile=profile)
    return evaluate(
        read.signals,
        detect=_detector_for(wt_path),
        phase=phase,
        promotions=getattr(profile, "lane_promotions", lambda: {})()
        if callable(getattr(profile, "lane_promotions", None)) else {},
        declared_nothing=read.declared_nothing,
        refusals=[str(r) for r in read.refusals],
    )


def format_output(report: LaneReport, change: Any = None) -> str:
    """Render the report for a human standing in front of a gate that just ran.

    A firing signal is printed together with the change's declared type, because either
    alone reads as normal: "a new module appeared" is ordinary, "this change is
    infrastructure" is ordinary, and only the pair is the finding.
    """
    declared_type = getattr(change, "change_type", None) or "unknown"
    lines: list[str] = []

    if report.declared_nothing:
        return ("No lane signals declared by this project — nothing was evaluated. "
                "This is not a clean result; it is an absent one.")

    for outcome in report.fired:
        # The declared lane is printed beside the declared change_type and NOT compared to
        # it: the mapping between a project's lane vocabulary and set-core's change types is
        # domain. Stated here rather than left implicit, because a reader seeing the two
        # names adjacent will otherwise assume the gate checked one against the other.
        lines.append(
            f"declared change_type={declared_type!r} "
            f"(signal's own lane label: {outcome.signal.lane!r}, not compared — see "
            f"LaneSignal.lane), but: {outcome.message}")
        for violation in outcome.violations:
            lines.append(f"    - {violation}")

    # Two buckets, not one. "this project publishes no answer" and "the answer came back
    # broken" are opposite statements about opposite subjects — the checkout versus the
    # change — and a reader told to tell them apart by reading the sentence is doing the
    # prose-parsed-as-fact job by hand. Neither is a pass; both are printed.
    for outcome in report.unevaluated:
        if outcome.reason_class == "not-published":
            continue
        marker = "[BLOCKED — UNEVALUATED]" if outcome.blocking else "[UNEVALUATED]"
        lines.append(f"{marker} {outcome.signal.name}: {outcome.reason}")
        if outcome.blocking:
            lines.append(
                "    this signal declares itself the ONLY enforcement of its defect class, "
                "so silence here is a hole rather than a lost early warning")

    for outcome in report.unevaluated:
        if outcome.reason_class != "not-published":
            continue
        marker = ("[BLOCKED — NOT PUBLISHED]" if outcome.blocking
                  else "[NOT PUBLISHED BY THIS TREE]")
        lines.append(f"{marker} {outcome.signal.name}: {outcome.reason}")

    for refusal in report.refusals:
        lines.append(f"[REFUSED] {refusal}")

    # Declared-but-unread keys are named, never interpreted. Keeping them and showing
    # nothing would move the silence one step later: the project would still believe the
    # framework acted on a field it merely stored. Naming them is also how a divergence
    # gets noticed — a project attaching a reference to its own canonical implementation
    # does so precisely so the two can be compared.
    for outcome in report.outcomes:
        if outcome.signal.extra:
            lines.append(
                f"[NOT READ] {outcome.signal.name}: declared "
                f"{sorted(outcome.signal.extra)} — this set-core version stores these "
                f"and interprets none of them")

    for name, added in report.baseline_growth:
        lines.append(f"[BASELINE GROWTH] {name}: {list(added)} — a baseline may only shrink; "
                     f"inheriting debt is what it is for, creating it is not")

    summary = report.summary()
    lines.append(
        f"signals: {summary['fired']} fired, {summary['did_not_fire']} did not fire, "
        f"{summary['unevaluated']} could not be evaluated, {summary['refused']} refused"
    )
    # Declared debt and checked debt are printed as two numbers, never one. "There is no
    # debt" and "the debt was not looked at" are opposite statements, and a single integer
    # lets the reassuring one win — in the summary line, which is the most-read copy.
    debt = (f"baselined debt: {summary['declared_debt']} declared, "
            f"{summary['checked_debt']} checked")
    if summary["unchecked_debt"]:
        debt += (f", {summary['unchecked_debt']} NOT CHECKED (no evaluation reached them — "
                 f"this is not a statement that they are resolved)")
    lines.append(debt)
    lines.append("This gate can show a contradiction; it cannot show there is none.")
    return "\n".join(lines)


def execute_lane_gate(change_name: str, change: Any, wt_path: str) -> Any:
    """Gate executor. Signature matches the other universal gates."""
    from .gate_runner import GateResult

    if not wt_path:
        return GateResult(GATE_NAME, "skipped", output="no worktree path")

    report = build_report(wt_path, change=change)
    output = format_output(report, change=change)

    if report.declared_nothing:
        # NOT "pass" — see the module docstring.
        return GateResult(GATE_NAME, "skipped", output=output)

    if report.blocks:
        return GateResult(GATE_NAME, "fail", output=output, retry_context=output)

    if report.fired:
        return GateResult(GATE_NAME, "warn-fail", output=output)

    # `pass` requires that every declared signal was actually EVALUATED. Nothing firing
    # while nothing could run is the same all-clear as the absent case wearing a better
    # status — and it is the shape the gate meets first in the real world, because
    # `_KIND_HANDLERS` is empty, so today every declared signal is unevaluated. Found by
    # running the gate against a declaring tree rather than by reading the code: it
    # answered `pass`, which the four rules in this module's docstring forbid.
    #
    # Strictness costs nothing here: `skipped` blocks nothing. It only refuses to claim a
    # clean result the gate did not earn.
    if report.unevaluated:
        return GateResult(GATE_NAME, "skipped", output=output)

    return GateResult(GATE_NAME, "pass", output=output)


def gate_definition():
    """The registry entry. Late import keeps this module free of a cycle."""
    from .gate_runner import GateDefinition

    return GateDefinition(
        GATE_NAME,
        execute_lane_gate,
        position="before:end",
        # No per-change_type defaults: a gate whose job is to doubt the declared type must
        # not be switched off by that same declaration. That would be the hole it exists
        # to close, wired in as configuration.
        defaults={},
    )
