"""The queue's rules — ordering, the freeze, what leaves, and what never does.

Each test names a direction of failure rather than a feature. The queue's job is
to be the only thing deciding what a reader looks at next, so every way it can
be wrong either wastes their attention or hides an agent that needs them, and
the second is the expensive one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from set_orch.fleet import judgment as j
from set_orch.fleet import state as agent_state
from set_orch.fleet.attention import COUNTDOWN_SECONDS, TYPING_WINDOW_SECONDS, Item, Queue

NOW = 1_000_000.0


def _subject(pid: int, project: str = "p", log: str | None = None) -> j.Subject:
    return j.Subject(pid=pid, project=project, state=agent_state.QUIET, session_log=log, label=f"a{pid}")


def _verdicts(**kinds) -> dict:
    return {int(pid): j.Verdict(pid=int(pid), verdict=v, source="model") for pid, v in kinds.items()}


def _result(verdicts, *, measured=True, reason=None, not_covered=()) -> j.PassResult:
    return j.PassResult(verdicts=verdicts, measured=measured, reason=reason, not_covered=list(not_covered))


def _states(*, ages: dict[int, float]) -> dict:
    return {pid: agent_state.AgentState(state=agent_state.QUIET, last_movement_age=age)
            for pid, age in ages.items()}


def _queue(pids_ages: dict[int, float], projects: dict[int, str] | None = None) -> tuple[Queue, list]:
    projects = projects or {}
    subjects = [_subject(p, projects.get(p, "p")) for p in pids_ages]
    q = Queue()
    q.update(subjects, _result(_verdicts(**{str(p): j.ASKING for p in pids_ages})),
             states=_states(ages=pids_ages), now=NOW)
    return q, subjects


# --------------------------------------------------------------------------- #
# what is in the queue
# --------------------------------------------------------------------------- #

def test_a_completion_report_is_counted_not_queued():
    """12 of 17 quiet agents were this, measured. Queueing them would put a
    dozen 'done' messages in front of every real question."""
    q = Queue()
    q.update([_subject(1), _subject(2)],
             _result(_verdicts(**{"1": j.ASKING, "2": j.FINISHED})),
             states=_states(ages={1: 10, 2: 10}), now=NOW)
    assert [i.pid for i in q.ordered()] == [1]
    assert q.counts.idle == 1
    assert q.counts.queued == 1


def test_an_unclassified_agent_is_counted_and_not_queued():
    q = Queue()
    q.update([_subject(1)], _result(_verdicts(**{"1": j.UNCLASSIFIED})),
             states=_states(ages={1: 10}), now=NOW)
    assert q.ordered() == []
    assert q.counts.unclassified == 1


# --------------------------------------------------------------------------- #
# order
# --------------------------------------------------------------------------- #

def test_a_fresh_blockage_outranks_an_old_one():
    q, _ = _queue({1: 2400.0, 2: 120.0})  # 40 minutes vs 2 minutes
    assert [i.pid for i in q.ordered()] == [2, 1]


def test_a_project_is_exhausted_before_the_next_one_is_entered():
    """The reader's context switch is the expensive thing, not the machine's."""
    q, _ = _queue({1: 300.0, 2: 60.0, 3: 120.0},
                  projects={1: "alpha", 2: "beta", 3: "alpha"})
    q.present(1)
    order = [i.pid for i in q.ordered()]
    # The claim is the GROUPING of what the reader has NOT seen: alpha's unseen
    # item comes before beta's, even though beta's is the freshest of the three.
    # Item 1 is behind both because it was presented and not dealt with —
    # demotion outranks the project, which is what lets `later` leave it.
    assert order == [3, 2, 1], order


def test_a_deferred_item_does_not_preempt_its_way_back_onto_the_screen():
    """Measured in the browser 2026-08-20, one fix downstream of the last one.

    `later` handed the screen to the next item, and the deferred item — which is
    the freshest blockage there is — offered to take it back four seconds later.
    """
    q, _ = _queue({1: 60.0, 2: 300.0}, projects={1: "alpha", 2: "beta"})
    q.present(1)
    q.defer(1)                       # 2 is now on screen; 1 is fresher than it
    assert q.preemption(seconds_since_input=None) is None


def test_deferral_leaves_the_project_when_the_only_unseen_item_is_elsewhere():
    """`later` that returns the same item is a dead button.

    Measured in the browser 2026-08-20: two queued items, two projects, and
    deferring the presented one put it straight back on screen — its project
    held the top rank BY VIRTUE OF that same item.
    """
    q, _ = _queue({1: 60.0, 2: 300.0}, projects={1: "alpha", 2: "beta"})
    q.present(1)
    moved = q.defer(1)
    assert moved is not None and moved.pid == 2, moved
    assert [i.pid for i in q.ordered()] == [2, 1]


def test_a_presented_item_ranks_below_an_unseen_one_of_the_same_project():
    """Their silence is evidence they will not answer it now."""
    q, _ = _queue({1: 60.0, 2: 300.0})
    q.present(1)          # 1 is fresher, so it would otherwise stay first
    q.defer(1)
    # The product claim is what the reader now SEES, not the raw ordering: the
    # unseen item takes the screen. (Deferred item 1 is still queued — nothing
    # leaves except by being dealt with.)
    assert q.head().pid == 2
    assert 1 in {i.pid for i in q.ordered()}


# --------------------------------------------------------------------------- #
# nothing leaves except by being dealt with
# --------------------------------------------------------------------------- #

def test_a_preempted_item_returns_and_stays_counted():
    q, _ = _queue({1: 300.0, 2: 60.0})
    q.present(1)
    assert q.preemption(seconds_since_input=None) is not None
    q.present(2)
    assert 1 in {i.pid for i in q.ordered()}
    assert q.counts.queued == 2


def test_a_dismissed_item_leaves_and_is_counted():
    q, _ = _queue({1: 60.0, 2: 300.0})
    q.dismiss(1)
    assert [i.pid for i in q.ordered()] == [2]
    assert q.counts.dismissed == 1


def test_a_dismissed_item_does_not_come_back_on_the_next_cycle():
    q, subjects = _queue({1: 60.0})
    q.dismiss(1)
    q.update(subjects, _result(_verdicts(**{"1": j.ASKING})), states=_states(ages={1: 60}), now=NOW)
    assert q.ordered() == []


def test_a_vanished_agent_leaves_and_it_is_not_recorded_as_an_answer(caplog):
    caplog.set_level("INFO")
    q, _ = _queue({1: 60.0, 2: 90.0})
    q.update([_subject(2)], _result(_verdicts(**{"2": j.ASKING})),
             states=_states(ages={2: 90}), now=NOW)
    assert [i.pid for i in q.ordered()] == [2]
    assert "gone" in "\n".join(r.getMessage() for r in caplog.records)


def test_an_unmeasured_pass_does_not_empty_the_queue():
    """The calm screen this feature exists to prevent."""
    q, subjects = _queue({1: 60.0})
    q.update(subjects, _result(_verdicts(**{"1": j.UNCLASSIFIED}), measured=False, reason="failed"),
             states=_states(ages={1: 60}), now=NOW)
    assert [i.pid for i in q.ordered()] == [1]
    assert q.counts.judgment_measured is False
    assert q.counts.judgment_reason == "failed"


def test_a_measured_pass_that_no_longer_says_asking_does_remove_it():
    """The other direction, so the rule above is not simply 'never remove'."""
    q, subjects = _queue({1: 60.0})
    q.update(subjects, _result(_verdicts(**{"1": j.FINISHED}), measured=True),
             states=_states(ages={1: 60}), now=NOW)
    assert q.ordered() == []


def test_a_queued_items_position_is_not_re_dated_every_cycle():
    """Otherwise a long-waiting item is 'fresh' forever and never ages."""
    q, subjects = _queue({1: 600.0, 2: 60.0})
    first = q.ordered()[0].pid
    q.update(subjects, _result(_verdicts(**{"1": j.ASKING, "2": j.ASKING})),
             states=_states(ages={1: 1, 2: 1}), now=NOW + 60)
    assert q.ordered()[0].pid == first


# --------------------------------------------------------------------------- #
# only resuming counts as dealt with
# --------------------------------------------------------------------------- #

def _log(tmp_path: Path, entries) -> str:
    p = tmp_path / "s.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return str(p)


def _said(role: str, text: str, ts: float) -> dict:
    from datetime import datetime, timezone
    return {"type": role, "timestamp": datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z"),
            "message": {"role": role, "content": [{"type": "text", "text": text}]}}


def test_an_interrupt_does_not_advance_the_queue(tmp_path):
    q, _ = _queue({1: 60.0, 2: 300.0})
    q.present(1)
    log = _log(tmp_path, [_said("assistant", "Shall I?", NOW - 120),
                          _said("user", "[Request interrupted by user]", NOW - 10)])
    assert q.advance_if_dealt_with(log) is False
    assert q.head().pid == 1


def test_a_real_answer_advances_the_queue(tmp_path):
    q, _ = _queue({1: 60.0, 2: 300.0})
    q.present(1)
    log = _log(tmp_path, [_said("assistant", "Shall I?", NOW - 120),
                          _said("user", "yes", NOW - 10),
                          _said("assistant", "Starting.", NOW - 5)])
    assert q.advance_if_dealt_with(log) is True
    assert q.head().pid == 2


def test_an_unreadable_log_does_not_advance_the_queue(tmp_path):
    """Unknown is not 'dealt with'. Advancing here drops an unanswered item."""
    q, _ = _queue({1: 60.0})
    q.present(1)
    assert q.advance_if_dealt_with(str(tmp_path / "nope.jsonl")) is False
    assert q.head().pid == 1


# --------------------------------------------------------------------------- #
# typing is the guard
# --------------------------------------------------------------------------- #

def test_typing_suspends_every_switch():
    q, _ = _queue({1: 300.0, 2: 60.0})
    q.present(1)
    assert q.preemption(seconds_since_input=TYPING_WINDOW_SECONDS - 1) is None


def test_a_silent_screen_is_preempted_by_a_fresher_blockage():
    q, _ = _queue({1: 300.0, 2: 60.0})
    q.present(1)
    offer = q.preemption(seconds_since_input=TYPING_WINDOW_SECONDS + 1)
    assert offer is not None and offer.pid == 2


def test_a_silent_screen_holding_the_freshest_item_is_not_preempted():
    """Freshness is the whole justification; without it there is no case."""
    q, _ = _queue({1: 60.0, 2: 300.0})
    q.present(1)
    assert q.preemption(seconds_since_input=10_000) is None


def test_never_typed_is_not_protection():
    q, _ = _queue({1: 300.0, 2: 60.0})
    q.present(1)
    assert q.preemption(seconds_since_input=None) is not None


def test_refusing_an_interruption_silences_it_only_while_the_screen_is_unchanged():
    q, _ = _queue({1: 300.0, 2: 60.0, 3: 30.0})
    q.present(1)
    q.refuse(2)
    offer = q.preemption(seconds_since_input=None)
    assert offer is not None and offer.pid == 3   # 2 refused, 3 still offered
    q.present(3)
    q.present(1)
    again = q.preemption(seconds_since_input=None)
    assert again is not None and again.pid in (2, 3)


# --------------------------------------------------------------------------- #
# history
# --------------------------------------------------------------------------- #

def test_stepping_back_re_presents_and_marks_nothing_dealt_with():
    q, _ = _queue({1: 300.0, 2: 60.0})
    q.present(1)
    q.present(2)
    assert q.back().pid == 1
    assert q.counts.queued == 2


def test_forward_is_bounded_by_the_queues_own_position():
    q, _ = _queue({1: 300.0, 2: 60.0})
    q.present(1)
    q.present(2)
    assert q.can_go_forward() is False
    q.back()
    assert q.can_go_forward() is True
    assert q.forward().pid == 2
    assert q.can_go_forward() is False


def test_back_skips_an_item_that_has_since_left_the_queue():
    q, _ = _queue({1: 300.0, 2: 60.0, 3: 30.0})
    q.present(1)
    q.present(2)
    q.present(3)
    q.dismiss(2)
    assert q.back().pid == 1


def test_back_is_unavailable_at_the_beginning():
    q, _ = _queue({1: 60.0})
    q.present(1)
    assert q.can_go_back() is False
    assert q.back() is None


# --------------------------------------------------------------------------- #
# confidentiality
# --------------------------------------------------------------------------- #

def test_no_queue_record_carries_session_content():
    """Identity, class, timestamps. Nothing a consumer wrote."""
    q, _ = _queue({1: 60.0})
    item = q.ordered()[0]
    assert set(vars(item)) == {
        "pid", "project", "label", "source", "blocked_since", "blockage_point", "presented_count",
    }


def test_the_countdown_length_is_declared_not_scattered():
    assert COUNTDOWN_SECONDS > 0 and TYPING_WINDOW_SECONDS > COUNTDOWN_SECONDS


def test_a_working_agent_is_never_queued_whatever_a_verdict_says(caplog):
    """A guarantee the queue makes itself, not one it inherits.

    The candidate filter already excludes a working agent, so no such verdict
    can arrive today. That is the reason to write the rule down HERE: the
    queue must not depend on an upstream filter staying correct for something
    it promises on its own.
    """
    caplog.set_level("WARNING")
    q = Queue()
    q.update([_subject(1)], _result(_verdicts(**{"1": j.ASKING})),
             states={1: agent_state.AgentState(state=agent_state.WORKING, tool="Bash")}, now=NOW)
    assert q.ordered() == []
    assert "working" in "\n".join(r.getMessage() for r in caplog.records)


def test_idle_is_a_population_count_not_a_per_pass_one():
    """Found by WATCHING the live screen, not by a test.

    `idle` fell 12 → 9 → 1 across three cycles while nothing in the fleet
    changed. The candidate filter skips an agent whose log has not moved, so a
    count taken from one pass's verdicts shrinks as agents drop out of the pass
    — and it renders as agents ceasing to be idle. The count is about the
    population; the pass is about what was looked at this time.
    """
    subjects = [_subject(1), _subject(2)]
    q = Queue()
    q.update(subjects, _result(_verdicts(**{"1": j.FINISHED, "2": j.FINISHED})),
             states=_states(ages={1: 5, 2: 5}), now=NOW)
    assert q.counts.idle == 2
    # Next cycle: agent 2's log did not move, so it is not in the verdicts.
    q.update(subjects, _result(_verdicts(**{"1": j.FINISHED})),
             states=_states(ages={1: 5, 2: 5}), now=NOW + 60)
    assert q.counts.idle == 2


def test_an_agent_that_is_gone_stops_being_counted_idle():
    subjects = [_subject(1), _subject(2)]
    q = Queue()
    q.update(subjects, _result(_verdicts(**{"1": j.FINISHED, "2": j.FINISHED})),
             states=_states(ages={1: 5, 2: 5}), now=NOW)
    q.update([_subject(1)], _result(_verdicts(**{"1": j.FINISHED})),
             states=_states(ages={1: 5}), now=NOW + 60)
    assert q.counts.idle == 1


def test_the_counts_say_whether_anything_has_been_counted_yet():
    """A zero before the first cycle is a default, not a measurement."""
    q = Queue()
    assert q.counts.counted is False
    q.update([_subject(1)], _result(_verdicts(**{"1": j.FINISHED})),
             states=_states(ages={1: 5}), now=NOW)
    assert q.counts.counted is True
