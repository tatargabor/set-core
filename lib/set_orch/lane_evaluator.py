"""Evaluating lane signals — three outcomes, a shrink-only baseline, and no verdict.

The companion to `lane_signals.py`. That module reads what a project declared; this one
decides what a signal says about one change, and — just as importantly — what it must
never say.

**Three outcomes, not two.** A signal FIRED, DID NOT FIRE, or COULD NOT BE EVALUATED.
Collapsing the third into the second is a false absence in the one place a reader would
believe it: "no violations" about a signal whose input was missing. The unevaluated ones
are counted separately and reported by name.

**No overall verdict.** This gate can prove a contradiction; it cannot prove the absence of
one. A change whose lane is wrong in a way no declared signal covers passes silently, so a
summary field asserting the lane is correct would assert exactly what nobody measured.
`LaneReport` therefore has no `ok`, `ready` or `lane_correct` field, and a test forbids one
being added later.

**The baseline may only shrink.** A signal introduced into a real repository fires on
dozens of pre-existing cases on its first day and gets switched off within the week —
taking the warning with it. The baseline records those as debt so the gate stays quiet
about them, and refuses to grow: a change that adds a violation *and* baselines it fails,
regardless of severity. Outstanding debt is reported even when nothing new fires, because a
quiet zero is how a backlog stops being anyone's problem.

**WARN until a measurement promotes it.** Every signal starts at WARN. ENFORCE requires the
project's own declared measurement to be recorded; an unproven promotion is refused and the
signal evaluates at WARN, with the refusal reported rather than silently downgraded.

**Scope is obeyed, and out-of-scope is not a pass.** A signal declared for per-change
verification is not evaluated during a merge-time integration run, and its absence there is
recorded as not-evaluated. An unscoped signal would re-judge work it has already judged,
producing noise proportional to the project's age and pressuring the baseline upward — the
one direction it may not move.

See `openspec/changes/lane-contradiction-detection/` for the requirements.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

from .lane_signals import LaneSignal

logger = logging.getLogger(__name__)

FIRED = "fired"
DID_NOT_FIRE = "did_not_fire"
UNEVALUATED = "unevaluated"

WARN = "warn"
ENFORCE = "enforce"


class BaselineGrowth(Exception):
    """A change tried to add an entry to a baseline.

    Its own exception type because it fails the gate independently of severity: a WARN
    signal still blocks here. Suppressing a violation you just introduced is not the same
    act as inheriting one, and only the second is what a baseline is for.
    """


@dataclass
class SignalOutcome:
    signal: LaneSignal
    status: str
    violations: tuple = ()
    reason: str = ""
    severity: str = WARN

    @property
    def message(self) -> str:
        """What the reader sees when this signal fires.

        Carries the triggering case and the way to silence THIS signal. The person reading
        it is reading it because it just fired, and that is the only moment the reason is
        worth anything — if the rationale lives one indirection away, the fastest available
        response is a blanket bypass. So the narrow one is offered here, where it is
        looked for.
        """
        if self.status != FIRED:
            return ""
        head = f"[{self.severity.upper()}] {self.signal.name}: {len(self.violations)} violation(s)"
        why = f"why this signal exists: {self.signal.triggering_case}"
        if not self.signal.is_explained:
            why += "  (dated but unexplained — the gate has NOT checked any justification)"
        how = f"to silence only this signal: SET_LANE_SKIP={self.signal.name}"
        return "\n".join((head, why, how))


@dataclass
class LaneReport:
    """The result of evaluating every declared signal against one change.

    Deliberately has no field asserting the lane is correct — see the module docstring.
    """

    outcomes: list = field(default_factory=list)
    refusals: list = field(default_factory=list)
    declared_nothing: bool = True

    #: Baseline entries the project DECLARED, summed straight from the declarations. A
    #: baseline is a declared quantity, so it is read from the declaration — never
    #: accumulated along the evaluation path, which is how it used to be counted and why it
    #: reported `0` for a project declaring ten. The increment sat after three `continue`s
    #: (out of scope / raised / could not decide), so with no condition handlers registered
    #: **every** project saw zero debt, in the summary line — the most-read copy.
    declared_debt: int = 0

    #: How much of that debt was actually LOOKED AT. Separate from `declared_debt` on
    #: purpose: "there is no debt" and "we could not check the debt" are opposite
    #: statements, and collapsing them into one integer makes the reassuring one win.
    checked_debt: int = 0

    baseline_growth: tuple = ()

    @property
    def fired(self) -> list:
        return [o for o in self.outcomes if o.status == FIRED]

    @property
    def unevaluated(self) -> list:
        return [o for o in self.outcomes if o.status == UNEVALUATED]

    @property
    def did_not_fire(self) -> list:
        """Only signals that RAN and found nothing. Unevaluated ones are not in here."""
        return [o for o in self.outcomes if o.status == DID_NOT_FIRE]

    @property
    def blocks(self) -> bool:
        """Whether the gate fails. Baseline growth blocks regardless of severity."""
        if self.baseline_growth:
            return True
        return any(o.severity == ENFORCE for o in self.fired)

    @property
    def unchecked_debt(self) -> int:
        """Declared debt that no evaluation reached. Reported, never silently dropped."""
        return max(0, self.declared_debt - self.checked_debt)

    def summary(self) -> dict:
        """Counts, never a verdict. `evaluated` excludes what could not be decided."""
        return {
            "declared_nothing": self.declared_nothing,
            "fired": len(self.fired),
            "did_not_fire": len(self.did_not_fire),
            "unevaluated": len(self.unevaluated),
            "refused": len(self.refusals),
            "declared_debt": self.declared_debt,
            "checked_debt": self.checked_debt,
            "unchecked_debt": self.unchecked_debt,
            "baseline_growth": len(self.baseline_growth),
        }


def resolve_severity(signal: LaneSignal, promotions: Optional[dict] = None) -> tuple:
    """Return `(severity, refusal_reason)`.

    ENFORCE only when the project recorded the measurement its own promotion condition
    names. A promotion without evidence is refused AND reported — silently downgrading it
    would leave a project believing a signal blocks when it does not.
    """
    wanted = str((signal.promotion or {}).get("severity", WARN)).lower()
    if wanted != ENFORCE:
        return WARN, ""

    evidence = (promotions or {}).get(signal.name)
    if not evidence:
        reason = (f"{signal.name}: promotion to enforce refused — the declared measurement "
                  f"({(signal.promotion or {}).get('measure', 'unspecified')}) is not recorded")
        # Shape, not content — the reason quotes the project's own declared measurement,
        # and it already reaches the developer through the returned refusal.
        logger.warning("lane signal promotion to enforce refused: measurement not recorded")
        return WARN, reason
    return ENFORCE, ""


def in_scope(signal: LaneSignal, phase: str) -> bool:
    """Whether this signal runs in the current phase."""
    return signal.scope == phase


def evaluate(signals: Iterable[LaneSignal],
             detect: Callable[[LaneSignal], Optional[Iterable[str]]],
             phase: str = "per-change-verification",
             promotions: Optional[dict] = None,
             baseline_additions: Optional[dict] = None,
             declared_nothing: bool = False,
             refusals: Optional[list] = None) -> LaneReport:
    """Evaluate declared signals against one change.

    `detect` runs a signal's condition and returns the violations it found, or **None**
    when it could not decide — the distinction the three outcomes rest on. Returning an
    empty list means "ran, found nothing"; returning None means "could not run", and the
    two must never collapse.

    `baseline_additions` maps a signal name to entries this change ADDS to its baseline.
    Any entry there fails the gate: inheriting debt is what a baseline is for, creating it
    is not.
    """
    report = LaneReport(declared_nothing=declared_nothing,
                        refusals=list(refusals or []))
    growth = []

    for signal in signals:
        # Counted BEFORE any `continue`: a baseline is a declared quantity, readable from
        # the declaration itself. Accumulating it along the evaluation path made an
        # unevaluable signal report zero debt — see `LaneReport.declared_debt`.
        report.declared_debt += len(set(signal.baseline))

        severity, refusal = resolve_severity(signal, promotions)
        if refusal:
            report.refusals.append(refusal)

        added = tuple((baseline_additions or {}).get(signal.name) or ())
        if added:
            growth.append((signal.name, added))
            logger.error("lane signal: baseline growth attempted (%d entr(y|ies))",
                         len(added))

        if not in_scope(signal, phase):
            report.outcomes.append(SignalOutcome(
                signal, UNEVALUATED, reason=f"out of scope here (declared for {signal.scope!r}, "
                                            f"running {phase!r})", severity=severity))
            continue

        try:
            found = detect(signal)
        except Exception as exc:
            logger.warning("lane signal could not be evaluated: %s", type(exc).__name__)
            report.outcomes.append(SignalOutcome(
                signal, UNEVALUATED, reason=f"{type(exc).__name__}: {exc}", severity=severity))
            continue

        if found is None:
            report.outcomes.append(SignalOutcome(
                signal, UNEVALUATED, reason="the condition's input is absent",
                severity=severity))
            continue

        baselined = set(signal.baseline)
        report.checked_debt += len(baselined)
        fresh = tuple(v for v in found if v not in baselined)

        if fresh:
            report.outcomes.append(SignalOutcome(signal, FIRED, violations=fresh,
                                                 severity=severity))
        else:
            report.outcomes.append(SignalOutcome(signal, DID_NOT_FIRE, severity=severity))

    report.baseline_growth = tuple(growth)
    logger.info("lane evaluation: %s", report.summary())
    return report
