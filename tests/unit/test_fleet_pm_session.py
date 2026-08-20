"""PM mode's wiring: off means no invocation, and a failed cycle is not calm.

The thin layer, so the tests here are about the few decisions that live in it
rather than about ordering or classification — those have their own files.
"""

from __future__ import annotations

import pytest

from set_orch.fleet import judgment as j
from set_orch.fleet import pm as pm_mod
from set_orch.fleet import state as agent_state


@pytest.fixture
def session(monkeypatch):
    s = pm_mod.PmSession()
    calls = {"subjects": 0, "passes": 0}

    def _subjects(self=None):
        calls["subjects"] += 1
        subjects = [j.Subject(pid=1, project="p", state=agent_state.QUIET, session_log=None, label="a1")]
        states = {1: agent_state.AgentState(state=agent_state.QUIET, last_movement_age=30.0)}
        return subjects, states

    def _run_pass(subjects, watermarks, **kw):
        calls["passes"] += 1
        return j.PassResult(
            verdicts={1: j.Verdict(pid=1, verdict=j.ASKING, source="model")}, measured=True,
        )

    monkeypatch.setattr(pm_mod.PmSession, "_subjects", lambda self: _subjects())
    monkeypatch.setattr(pm_mod.judgment, "run_pass", _run_pass)
    return s, calls


def test_off_means_no_invocation(session):
    s, calls = session
    assert s.cycle() is False
    assert calls["passes"] == 0
    assert calls["subjects"] == 0


def test_turning_the_mode_on_touches_no_agent(session, monkeypatch):
    """A toggle that also acted on agents is one nobody dares press."""
    s, _ = session
    from set_orch.fleet import instruct as fleet_instruct

    monkeypatch.setattr(fleet_instruct, "send_instruction",
                        lambda *a, **k: pytest.fail("enabling must not instruct anyone"))
    monkeypatch.setattr(fleet_instruct, "instruct_agent",
                        lambda *a, **k: pytest.fail("enabling must not instruct anyone"))
    s.enable()
    assert s.enabled is True


def test_the_cycle_period_is_enforced_server_side(session):
    """Client-side rate limiting is one refresh away from not existing."""
    s, calls = session
    s.enable()
    assert s.cycle(now=1000.0) is True
    assert s.cycle(now=1000.0 + j.CYCLE_SECONDS - 1) is False
    assert s.cycle(now=1000.0 + j.CYCLE_SECONDS + 1) is True
    assert calls["passes"] == 2


def test_force_overrides_the_period_so_enabling_shows_something_at_once(session):
    s, calls = session
    s.enable()
    s.cycle(now=1000.0)
    assert s.cycle(force=True, now=1000.0) is True
    assert calls["passes"] == 2


def test_the_snapshot_separates_an_unmeasured_judgment_from_an_empty_queue(monkeypatch):
    s = pm_mod.PmSession()
    monkeypatch.setattr(
        pm_mod.PmSession, "_subjects",
        lambda self: ([j.Subject(pid=1, project="p", state=agent_state.QUIET)],
                      {1: agent_state.AgentState(state=agent_state.QUIET, last_movement_age=5.0)}),
    )
    monkeypatch.setattr(
        pm_mod.judgment, "run_pass",
        lambda subjects, watermarks, **kw: j.PassResult(
            verdicts={}, measured=False, reason="the judgment pass failed (RuntimeError)"),
    )
    s.enable()
    s.cycle(force=True, now=1.0)
    snap = s.snapshot()
    assert snap["presented"] is None
    assert snap["counts"]["judgment_measured"] is False
    assert snap["counts"]["judgment_reason"]
    assert snap["last_error"]


def test_a_fleet_that_cannot_be_read_does_not_raise_and_says_so(monkeypatch):
    s = pm_mod.PmSession()

    def boom(self):
        raise OSError("/home/someone/secret/path")

    monkeypatch.setattr(pm_mod.PmSession, "_subjects", boom)
    s.enable()
    assert s.cycle(force=True) is False
    # The class, never the message: discovery walks consumer trees and its
    # errors carry paths.
    assert "OSError" in s._last_error
    assert "secret" not in s._last_error


def test_the_snapshot_shape_is_stable_and_carries_no_session_text(session):
    s, _ = session
    s.enable()
    s.cycle(force=True, now=1.0)
    snap = s.snapshot(seconds_since_input=999.0)
    assert set(snap) == {
        "enabled", "presented", "queued", "counts", "can_go_back", "can_go_forward",
        "pending_switch", "last_cycle", "last_error",
    }
    assert set(snap["presented"]) == {
        "pid", "project", "label", "source", "blocked_since", "blockage_point", "presented_count",
    }
