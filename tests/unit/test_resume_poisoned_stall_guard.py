"""Tests for the poisoned-stall-recovery guard in resume_change (F5).

Context from craftbrew-run-20260423-2223: auth-core-and-admin-gate died
with loop_status=stalled after running a session that accumulated
~12M tool-output tokens (v0-export reads + apply + build logs). The
supervisor re-dispatched and ralph resumed the preserved session, loading
the same poisoned context → 130% context_tokens_start → another stall.
Circular.

Fix: when a stall_reason indicates the agent died BECAUSE of the context
(dead_running_agent_*, dead_verify_agent, verify_timeout,
fix_loop_no_progress_*, token_runaway, context_overflow), resume_change
must force a fresh session — clear session_id in loop-state.json — so
Claude starts from a clean prompt.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from set_orch import dispatcher
from set_orch.state import Change, OrchestratorState, load_state, save_state


def _seed_stalled_change(tmp_path: Path, stall_reason: str | None = None,
                         session_id: str = "old-session-abc") -> str:
    """Seed a project with one stalled change + a preserved loop-state.json."""
    wt = tmp_path / "wt"
    (wt / ".set").mkdir(parents=True)
    # Preserved loop-state with an existing session_id
    loop_state = wt / ".set" / "loop-state.json"
    loop_state.write_text(json.dumps({
        "session_id": session_id,
        "change": "foo",
        "started_at": "2026-04-24T00:00:00+02:00",
        "resume_failures": 0,
    }))

    extras: dict = {}
    if stall_reason is not None:
        extras["stall_reason"] = stall_reason

    state = OrchestratorState(
        changes=[
            Change(
                name="foo", status="stalled",
                worktree_path=str(wt),
                depends_on=[], roadmap_item="", scope="",
                extras=extras,
            ),
        ],
    )
    sp = str(tmp_path / "state.json")
    save_state(state, sp)
    return sp


def _stubbed_resume(sp: str) -> None:
    """Call resume_change with the subprocess-y bits stubbed out."""
    # Just short-circuit every subprocess-touching helper so the function
    # exits after doing its book-keeping + session_id clearing.
    with (
        patch("set_orch.dispatcher._kill_existing_wt_loop"),
        patch("set_orch.dispatcher.run_git") as rg,
        patch("subprocess.Popen"),
        patch("subprocess.run"),
    ):
        rg.return_value.exit_code = 1  # force early return path
        try:
            dispatcher.resume_change(sp, "foo")
        except Exception:
            # Later phases of resume_change may crash without a real
            # worktree/claude binary — we don't care; the session_id
            # decision is made before any subprocess is invoked.
            pass


def _read_loop_session(sp: str) -> str | None:
    wt_path = load_state(sp).changes[0].worktree_path
    with open(f"{wt_path}/.set/loop-state.json") as f:
        return json.load(f).get("session_id")


def test_no_stall_reason_preserves_session(tmp_path: Path) -> None:
    """Default behaviour (no poisoned stall) leaves session_id intact."""
    sp = _seed_stalled_change(tmp_path, stall_reason=None)
    _stubbed_resume(sp)
    assert _read_loop_session(sp) == "old-session-abc"


def test_dead_running_agent_clears_session(tmp_path: Path) -> None:
    sp = _seed_stalled_change(tmp_path, stall_reason="dead_running_agent_stalled")
    _stubbed_resume(sp)
    assert _read_loop_session(sp) is None


def test_dead_running_agent_unknown_variant(tmp_path: Path) -> None:
    """Any 'dead_running_agent_*' variant triggers the guard."""
    sp = _seed_stalled_change(tmp_path, stall_reason="dead_running_agent_unknown")
    _stubbed_resume(sp)
    assert _read_loop_session(sp) is None


def test_dead_verify_agent_clears_session(tmp_path: Path) -> None:
    sp = _seed_stalled_change(tmp_path, stall_reason="dead_verify_agent")
    _stubbed_resume(sp)
    assert _read_loop_session(sp) is None


def test_verify_timeout_clears_session(tmp_path: Path) -> None:
    sp = _seed_stalled_change(tmp_path, stall_reason="verify_timeout")
    _stubbed_resume(sp)
    assert _read_loop_session(sp) is None


def test_fix_loop_no_progress_clears_session(tmp_path: Path) -> None:
    sp = _seed_stalled_change(tmp_path, stall_reason="fix_loop_no_progress_stalled")
    _stubbed_resume(sp)
    assert _read_loop_session(sp) is None


def test_token_runaway_clears_session(tmp_path: Path) -> None:
    sp = _seed_stalled_change(tmp_path, stall_reason="token_runaway_detected")
    _stubbed_resume(sp)
    assert _read_loop_session(sp) is None


def test_context_overflow_clears_session(tmp_path: Path) -> None:
    sp = _seed_stalled_change(tmp_path, stall_reason="context_overflow_detected")
    _stubbed_resume(sp)
    assert _read_loop_session(sp) is None


def test_benign_stall_preserves_session(tmp_path: Path) -> None:
    """A 'benign' stall reason (e.g. manual pause) does NOT clear session."""
    sp = _seed_stalled_change(tmp_path, stall_reason="operator_pause")
    _stubbed_resume(sp)
    # No poison prefix match → session should be left alone by the guard
    # (though other guardrails like session_age_min may still clear it).
    # With our fresh seed (started 2026-04-24T00:00), the session is recent,
    # so the other guardrails don't fire — session_id should survive.
    assert _read_loop_session(sp) == "old-session-abc"


def test_stall_reason_cleared_after_consumption(tmp_path: Path) -> None:
    """The stall_reason flag is cleared once resume_change acts on it."""
    sp = _seed_stalled_change(tmp_path, stall_reason="dead_running_agent_stalled")
    _stubbed_resume(sp)
    ch = load_state(sp).changes[0]
    # extras may not contain 'stall_reason' OR it may be None — both mean cleared
    assert (ch.extras.get("stall_reason") or None) is None
