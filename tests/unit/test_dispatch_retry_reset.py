"""Test that dispatch_change resets gate retry counters on fresh dispatch (F7).

A change that exhausted its verify/gate/build budget on a prior dispatch
(or had counters persisted across a sentinel restart) must start fresh.
merge_stall_attempts and ff_retry_count are deliberately NOT in the reset
set — the circuit-breaker and recover-merge-blocked paths own those.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from set_orch.dispatcher import dispatch_change
from set_orch.state import Change, OrchestratorState, load_state, save_state


def _field(ch, name, default=None):
    """Read a counter from the dataclass attr if present, else extras."""
    v = getattr(ch, name, None)
    if v is not None:
        return v
    return ch.extras.get(name, default)


def _seed_change_with_counters(tmp_path: Path, extras: dict) -> str:
    state = OrchestratorState(
        changes=[
            Change(
                name="foo", status="pending",
                depends_on=[], roadmap_item="", scope="test",
                extras=extras,
            ),
        ],
    )
    sp = str(tmp_path / "state.json")
    save_state(state, sp)
    return sp


@pytest.fixture(autouse=True)
def _chdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _run_dispatch(sp: str) -> None:
    """Invoke dispatch_change, bailing out right after the counter-reset block.

    We patch `run_git` (first heavy call after the reset loop at
    dispatcher.py:2161) to raise SystemExit — the counter resets have
    already been persisted before this point, so we can assert against
    them without mocking the whole agent-spawn path.
    """
    with patch(
        "set_orch.dispatcher.run_git",
        side_effect=SystemExit("bail"),
    ):
        try:
            dispatch_change(sp, "foo")
        except SystemExit:
            pass
        except Exception:
            # Any later crash is fine — we only care that the reset block ran
            pass


def test_verify_retry_count_reset(tmp_path: Path) -> None:
    sp = _seed_change_with_counters(tmp_path, {"verify_retry_count": 2})
    _run_dispatch(sp)
    ch = load_state(sp).changes[0]
    assert _field(ch, "verify_retry_count") == 0


def test_gate_retry_count_reset(tmp_path: Path) -> None:
    sp = _seed_change_with_counters(tmp_path, {"gate_retry_count": 3})
    _run_dispatch(sp)
    ch = load_state(sp).changes[0]
    assert _field(ch, "gate_retry_count") == 0


def test_build_fix_attempt_count_reset(tmp_path: Path) -> None:
    sp = _seed_change_with_counters(tmp_path, {"build_fix_attempt_count": 4})
    _run_dispatch(sp)
    ch = load_state(sp).changes[0]
    assert _field(ch, "build_fix_attempt_count") == 0


def test_merge_stall_attempts_NOT_reset(tmp_path: Path) -> None:
    """Circuit-breaker counter must survive re-dispatch — monotonic by design."""
    sp = _seed_change_with_counters(tmp_path, {"merge_stall_attempts": 4})
    _run_dispatch(sp)
    ch = load_state(sp).changes[0]
    assert _field(ch, "merge_stall_attempts") == 4


def test_ff_retry_count_NOT_reset_here(tmp_path: Path) -> None:
    """ff_retry_count reset is owned by _recover_merge_blocked_safe, not dispatch.

    Resetting here as well would double-reset and re-enable the toggle bug
    the F1 guard was designed to fix.
    """
    sp = _seed_change_with_counters(tmp_path, {"ff_retry_count": 2})
    _run_dispatch(sp)
    ch = load_state(sp).changes[0]
    assert _field(ch, "ff_retry_count") == 2


def test_all_reset_together(tmp_path: Path) -> None:
    """A change with all three budgets exhausted gets all three reset at once."""
    sp = _seed_change_with_counters(tmp_path, {
        "verify_retry_count": 2,
        "gate_retry_count": 3,
        "build_fix_attempt_count": 4,
        "merge_stall_attempts": 5,      # NOT reset
        "ff_retry_count": 1,            # NOT reset
    })
    _run_dispatch(sp)
    ch = load_state(sp).changes[0]
    assert _field(ch, "verify_retry_count") == 0
    assert _field(ch, "gate_retry_count") == 0
    assert _field(ch, "build_fix_attempt_count") == 0
    assert _field(ch, "merge_stall_attempts") == 5
    assert _field(ch, "ff_retry_count") == 1


def test_fresh_change_with_no_counters_still_works(tmp_path: Path) -> None:
    """A brand-new change (no prior counters) must not crash on the reset."""
    sp = _seed_change_with_counters(tmp_path, {})
    _run_dispatch(sp)
    ch = load_state(sp).changes[0]
    # Reset writes 0; the fields now exist with value 0
    assert _field(ch, "verify_retry_count") == 0
    assert _field(ch, "gate_retry_count") == 0
    assert _field(ch, "build_fix_attempt_count") == 0
