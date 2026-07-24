"""The evaluator: three outcomes, a baseline that only shrinks, and no verdict.

Each test targets one requirement of `lane-contradiction-detection`, and every guard is
checked by mutation — a test that also passes without its guard proves nothing.
"""

import pytest

from set_orch import lane_evaluator as ev
from set_orch.lane_signals import LaneSignal


def _signal(name="sig", baseline=(), scope="per-change-verification", promotion=None,
            triggering="2026-07-20 DEF-77: a fix shipped with no regression test"):
    return LaneSignal(
        name=name, lane="restoring",
        condition={"kind": "fixed_defect_without_test"},
        scope=scope, baseline=tuple(baseline),
        promotion=promotion or {"measure": "half the signals real for two weeks"},
        triggering_case=triggering, exclusions=("docs/**",),
    )


# ── three outcomes, and why the third may not collapse into the second ─────────────

def test_an_unevaluable_signal_is_not_counted_as_did_not_fire():
    """`None` means "could not decide" and must stay distinct from "found nothing".

    Collapsing them reports calm about a signal whose input was missing — a false absence
    in the one place a reader would believe it.
    """
    report = ev.evaluate([_signal()], detect=lambda s: None)

    assert len(report.unevaluated) == 1
    assert report.did_not_fire == []
    assert report.summary()["unevaluated"] == 1
    assert report.summary()["did_not_fire"] == 0


def test_an_empty_list_means_ran_and_found_nothing():
    report = ev.evaluate([_signal()], detect=lambda s: [])

    assert len(report.did_not_fire) == 1
    assert report.unevaluated == []


def test_a_detector_that_raises_is_unevaluated_not_a_pass():
    def boom(signal):
        raise RuntimeError("the artefact is missing")

    report = ev.evaluate([_signal()], detect=boom)

    assert len(report.unevaluated) == 1
    assert "the artefact is missing" in report.unevaluated[0].reason


def test_no_overall_lane_correct_verdict_is_emitted():
    """A contradiction can be proven; its absence cannot. So there is no verdict field.

    Asserted against the report's own surface so that adding `ok` later fails here rather
    than quietly shipping a claim nobody measured.
    """
    report = ev.evaluate([_signal()], detect=lambda s: [])

    keys = set(report.summary()) | set(vars(report))
    for forbidden in ("ok", "ready", "green", "lane_correct", "passed", "verdict"):
        assert forbidden not in keys, f"the gate must not assert {forbidden!r}"


# ── the baseline: silent about inherited debt, loud about new debt ─────────────────

def test_a_baselined_violation_is_silent_and_a_new_one_is_not():
    signal = _signal(baseline=("DEF-11",))

    report = ev.evaluate([signal], detect=lambda s: ["DEF-11", "DEF-99"])

    assert len(report.fired) == 1
    assert report.fired[0].violations == ("DEF-99",)


def test_declared_and_checked_debt_are_reported_when_nothing_new_fires():
    """A quiet zero is how a backlog stops being anyone's problem."""
    signal = _signal(baseline=("DEF-11", "DEF-12"))

    report = ev.evaluate([signal], detect=lambda s: ["DEF-11", "DEF-12"])

    assert report.fired == []
    assert report.declared_debt == 2
    assert report.checked_debt == 2
    assert report.unchecked_debt == 0
    assert report.summary()["declared_debt"] == 2


def test_declared_debt_is_counted_even_when_NOTHING_could_be_evaluated():
    """The debt was counted along the evaluation path, so an unevaluable signal read 0.

    Measured by the peer against a real declaration: ten baselined entries reported as
    "outstanding baselined debt: 0". The increment sat after three `continue`s (out of
    scope / raised / could not decide), so with no condition handlers registered EVERY
    project would have seen zero — in the summary line, which is the most-read copy.

    A baseline is a DECLARED quantity. It is read from the declaration, never accumulated
    by whatever managed to run.
    """
    signal = _signal(baseline=("DEF-11", "DEF-12", "DEF-13"))

    report = ev.evaluate([signal], detect=lambda s: None)  # could not decide

    assert report.unevaluated != []
    assert report.declared_debt == 3, "declared debt must not depend on the evaluation"
    assert report.checked_debt == 0
    assert report.unchecked_debt == 3


def test_no_debt_and_unchecked_debt_are_two_different_statements():
    """Collapsed into one integer, the reassuring one wins."""
    empty = ev.evaluate([_signal(baseline=())], detect=lambda s: [])
    unchecked = ev.evaluate([_signal(baseline=("D-1",))], detect=lambda s: None)

    assert empty.summary()["declared_debt"] == 0
    assert empty.summary()["unchecked_debt"] == 0

    assert unchecked.summary()["declared_debt"] == 1
    assert unchecked.summary()["unchecked_debt"] == 1
    assert empty.summary() != unchecked.summary(), (
        "a project with no debt and one whose debt was never looked at must not produce "
        "the same summary")


def test_an_out_of_scope_signals_debt_is_still_declared():
    """The first of the three `continue`s, checked on its own."""
    signal = _signal(baseline=("D-1", "D-2"), scope="merge-time")

    report = ev.evaluate([signal], detect=lambda s: [], phase="per-change-verification")

    assert report.declared_debt == 2
    assert report.checked_debt == 0


def test_growing_a_baseline_fails_the_gate_regardless_of_severity():
    """Inheriting debt is what a baseline is for; creating it is not.

    Independent of WARN/ENFORCE on purpose — otherwise the cheapest way to suppress a
    fresh violation is to add it to the list the gate promises not to look at.
    """
    signal = _signal(baseline=("DEF-11",))

    report = ev.evaluate([signal], detect=lambda s: ["DEF-11"],
                         baseline_additions={"sig": ["DEF-99"]})

    assert report.baseline_growth == (("sig", ("DEF-99",)),)
    assert report.blocks is True
    assert all(o.severity == ev.WARN for o in report.outcomes), "premise: still WARN"


# ── severity: WARN until a measurement promotes it ────────────────────────────────

def test_a_warn_signal_does_not_block():
    report = ev.evaluate([_signal()], detect=lambda s: ["DEF-99"])

    assert len(report.fired) == 1
    assert report.blocks is False


def test_promotion_without_the_recorded_measurement_is_refused_and_reported():
    signal = _signal(promotion={"severity": "enforce", "measure": "half real for two weeks"})

    report = ev.evaluate([signal], detect=lambda s: ["DEF-99"], promotions={})

    assert report.fired[0].severity == ev.WARN
    assert report.blocks is False
    assert any("promotion to enforce refused" in r for r in report.refusals), \
        "a silent downgrade leaves a project believing a signal blocks when it does not"


def test_promotion_with_the_recorded_measurement_enforces():
    signal = _signal(promotion={"severity": "enforce", "measure": "half real for two weeks"})

    report = ev.evaluate([signal], detect=lambda s: ["DEF-99"],
                         promotions={"sig": {"measured": "2026-07-24", "real": 0.6}})

    assert report.fired[0].severity == ev.ENFORCE
    assert report.blocks is True


# ── scope ─────────────────────────────────────────────────────────────────────────

def test_an_out_of_scope_signal_is_unevaluated_not_a_pass():
    signal = _signal(scope="per-change-verification")

    report = ev.evaluate([signal], detect=lambda s: pytest.fail("must not run"),
                         phase="merge-integration")

    assert len(report.unevaluated) == 1
    assert report.did_not_fire == []
    assert "out of scope" in report.unevaluated[0].reason


# ── the firing message ────────────────────────────────────────────────────────────

def test_a_firing_signal_states_why_it_exists_and_how_to_silence_only_itself():
    """The reader is reading because it fired; that is when the reason is worth anything.

    And the narrow bypass is offered here because a reader who cannot find it will find
    the blanket one.
    """
    signal = _signal(triggering="2026-07-20 DEF-77: a fix shipped with no regression test")

    report = ev.evaluate([signal], detect=lambda s: ["DEF-99"])
    message = report.fired[0].message

    assert "2026-07-20" in message and "DEF-77" in message
    assert "SET_LANE_SKIP=sig" in message


def test_an_unexplained_signal_says_the_gate_did_not_check_the_justification():
    """A bare date is legal, and the message refuses to imply the reasoning was verified."""
    signal = _signal(triggering="2026-01-01")

    report = ev.evaluate([signal], detect=lambda s: ["DEF-99"])

    assert "has NOT checked" in report.fired[0].message


def test_a_signal_that_did_not_fire_has_no_message():
    report = ev.evaluate([_signal()], detect=lambda s: [])

    assert report.did_not_fire[0].message == ""


# ── absence ───────────────────────────────────────────────────────────────────────

def test_a_project_declaring_nothing_is_not_reported_as_clean():
    report = ev.evaluate([], detect=lambda s: [], declared_nothing=True)

    assert report.summary()["declared_nothing"] is True
    assert report.summary()["fired"] == 0
    assert report.blocks is False


def test_refusals_from_the_reader_travel_into_the_report():
    """A refusal list nobody sees is how a project believes it is guarded by a signal
    that never loaded."""
    report = ev.evaluate([], detect=lambda s: [], refusals=["sig: missing scope"])

    assert report.summary()["refused"] == 1
