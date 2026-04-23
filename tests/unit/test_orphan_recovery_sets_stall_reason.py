"""Finding 4: recover_orphaned_changes must set stall_reason so F5's guard fires.

Without this, an orphan recovery that promotes the change to `stopped`
lets the next resume_change resume the poisoned session — F5 sees no
stall_reason and the guard never trips.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from set_orch.dispatcher import recover_orphaned_changes
from set_orch.state import Change, OrchestratorState, load_state, save_state


def _seed(tmp_path: Path, *, pid: int, pid_alive: bool) -> str:
    wt = tmp_path / "wt"
    wt.mkdir()
    state = OrchestratorState(
        changes=[
            Change(
                name="foo", status="running",
                worktree_path=str(wt),
                ralph_pid=pid,
                depends_on=[], roadmap_item="", scope="",
                extras={},
            ),
        ],
    )
    sp = str(tmp_path / "state.json")
    save_state(state, sp)
    return sp


@pytest.fixture
def sp(tmp_path):
    return _seed(tmp_path, pid=12345, pid_alive=False)


def test_orphan_recovery_sets_dead_agent_stall_reason(sp: str) -> None:
    """Orphan with dead PID → stall_reason starts with dead_running_agent_."""
    mock_check = MagicMock()
    mock_check.return_value.alive = False
    mock_check.return_value.match = False
    with patch("set_orch.dispatcher.check_pid", mock_check):
        recover_orphaned_changes(sp)
    ch = load_state(sp).changes[0]
    assert ch.status == "stopped"
    reason = ch.extras.get("stall_reason") or ""
    assert reason.startswith("dead_running_agent_"), reason


def test_orphan_recovery_preserves_stall_reason_on_alive_agent(tmp_path: Path) -> None:
    """When the PID is alive, nothing happens — no stall_reason written."""
    sp = _seed(tmp_path, pid=54321, pid_alive=True)
    mock_check = MagicMock()
    mock_check.return_value.alive = True
    mock_check.return_value.match = True
    with patch("set_orch.dispatcher.check_pid", mock_check):
        recover_orphaned_changes(sp)
    ch = load_state(sp).changes[0]
    assert ch.status == "running"  # untouched
    assert "stall_reason" not in ch.extras
