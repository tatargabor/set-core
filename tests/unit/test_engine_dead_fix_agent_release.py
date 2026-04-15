"""Test: _release_dead_fix_agent_issues resolves orphaned active issues.

Observed on craftbrew-run-20260415-0146: ISS-001 (state=diagnosed) and
ISS-002 (state=investigating) both had fix_agent_pid set. The fix agent
died mid-fix. Issues stayed active. Merger's _get_issue_owned_changes
still returned auth-and-accounts → merge queue skipped with "owned by
issue pipeline" every poll.

User had to resolve via registry API manually. Fix: orphan cleanup scans
active issues, checks fix_agent_pid liveness, auto-resolves the dead ones.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "lib"))


def _seed_registry(state_dir: Path, issues: list[dict]) -> Path:
    reg_dir = state_dir / ".set" / "issues"
    reg_dir.mkdir(parents=True, exist_ok=True)
    path = reg_dir / "registry.json"
    path.write_text(json.dumps({"issues": issues}))
    return path


def _dead_pid() -> int:
    """Return a PID that almost-certainly isn't ours. We use a high number
    unlikely to be in use; if it IS alive by coincidence, the test skips."""
    import os
    candidate = 999999
    try:
        os.kill(candidate, 0)
        # alive — very unlucky
        return 0
    except OSError:
        return candidate


def test_dead_fix_agent_issue_is_released(tmp_path: Path):
    from set_orch.engine import _release_dead_fix_agent_issues

    state_file = tmp_path / "orchestration-state.json"
    state_file.write_text(json.dumps({"status": "running", "changes": []}))

    dead = _dead_pid()
    if not dead:
        import pytest
        pytest.skip("could not find a reliably-dead PID")

    _seed_registry(tmp_path, [
        {
            "id": "ISS-001", "state": "diagnosed", "fix_agent_pid": dead,
            "affected_change": "auth-and-accounts", "error_summary": "stuck",
        },
        {
            "id": "ISS-002", "state": "investigating", "fix_agent_pid": dead,
            "affected_change": "auth-and-accounts", "error_summary": "stuck",
        },
    ])
    released = _release_dead_fix_agent_issues(str(state_file))
    assert released == 2

    data = json.loads((tmp_path / ".set" / "issues" / "registry.json").read_text())
    for iss in data["issues"]:
        assert iss["state"] == "resolved"
        assert iss["fix_agent_pid"] is None
        assert iss.get("resolved_at")


def test_live_fix_agent_is_left_alone(tmp_path: Path):
    from set_orch.engine import _release_dead_fix_agent_issues

    import os
    state_file = tmp_path / "orchestration-state.json"
    state_file.write_text(json.dumps({"status": "running", "changes": []}))

    # Our own PID is guaranteed alive.
    my_pid = os.getpid()
    _seed_registry(tmp_path, [
        {
            "id": "ISS-001", "state": "fixing", "fix_agent_pid": my_pid,
            "affected_change": "x", "error_summary": "running",
        },
    ])
    released = _release_dead_fix_agent_issues(str(state_file))
    assert released == 0

    data = json.loads((tmp_path / ".set" / "issues" / "registry.json").read_text())
    assert data["issues"][0]["state"] == "fixing"
    assert data["issues"][0]["fix_agent_pid"] == my_pid


def test_no_fix_agent_pid_is_left_alone(tmp_path: Path):
    """Issues without fix_agent_pid haven't started a fix yet — the natural
    state machine handles them. Only release when a FIX was started but the
    worker died."""
    from set_orch.engine import _release_dead_fix_agent_issues

    state_file = tmp_path / "orchestration-state.json"
    state_file.write_text(json.dumps({"status": "running", "changes": []}))

    _seed_registry(tmp_path, [
        {"id": "ISS-001", "state": "diagnosed", "fix_agent_pid": None,
         "affected_change": "x", "error_summary": "awaiting fix"},
        {"id": "ISS-002", "state": "investigating", "fix_agent_pid": 0,
         "affected_change": "y", "error_summary": "no pid yet"},
    ])
    released = _release_dead_fix_agent_issues(str(state_file))
    assert released == 0


def test_terminal_issues_are_left_alone(tmp_path: Path):
    """Issues already resolved/dismissed must not be touched."""
    from set_orch.engine import _release_dead_fix_agent_issues

    state_file = tmp_path / "orchestration-state.json"
    state_file.write_text(json.dumps({"status": "running", "changes": []}))

    dead = _dead_pid()
    if not dead:
        import pytest
        pytest.skip("dead-pid check raced")

    _seed_registry(tmp_path, [
        # dead pid but terminal state — leave alone
        {"id": "ISS-001", "state": "resolved", "fix_agent_pid": dead,
         "affected_change": "x"},
        {"id": "ISS-002", "state": "dismissed", "fix_agent_pid": dead,
         "affected_change": "y"},
    ])
    released = _release_dead_fix_agent_issues(str(state_file))
    assert released == 0


def test_missing_registry_is_no_op(tmp_path: Path):
    """No registry file → return 0 silently (fresh project, no issues)."""
    from set_orch.engine import _release_dead_fix_agent_issues

    state_file = tmp_path / "orchestration-state.json"
    state_file.write_text(json.dumps({"status": "running", "changes": []}))
    assert _release_dead_fix_agent_issues(str(state_file)) == 0
