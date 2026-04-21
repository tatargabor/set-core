from __future__ import annotations

from pathlib import Path

import pytest

from set_orch.forensics.resolver import NoSessionDirsError, resolve_run


def test_resolves_main_and_worktrees(run_layout):
    resolved = resolve_run(
        run_layout["run_id"],
        claude_projects_root=run_layout["claude_projects_root"],
        e2e_runs_root=run_layout["e2e_runs_root"],
    )
    assert resolved.main_session_dir == run_layout["main_session_dir"]
    assert set(resolved.worktree_session_dirs) == {"auth-setup", "cart-and-session"}
    assert resolved.worktree_session_dirs["auth-setup"] == run_layout["worktree_dirs"]["auth-setup"]
    assert resolved.worktree_session_dirs["cart-and-session"] == run_layout["worktree_dirs"]["cart-and-session"]
    assert resolved.orchestration_dir == run_layout["orchestration_dir"]


def test_collision_neighbour_not_picked_up(run_layout):
    resolved = resolve_run(
        run_layout["run_id"],
        claude_projects_root=run_layout["claude_projects_root"],
        e2e_runs_root=run_layout["e2e_runs_root"],
    )
    # The neighbour dir is `-...<run_id>x` (encoded with trailing `x`). It must NOT
    # appear in the worktree map and the main dir must be the correct one.
    for path in resolved.worktree_session_dirs.values():
        assert path != run_layout["collision_session_dir"]
    assert resolved.main_session_dir != run_layout["collision_session_dir"]


def test_missing_orchestration_dir_emits_warning_but_resolves_sessions(
    run_layout, capsys
):
    # Delete the orchestration dir.
    import shutil
    shutil.rmtree(run_layout["orchestration_dir"])

    resolved = resolve_run(
        run_layout["run_id"],
        claude_projects_root=run_layout["claude_projects_root"],
        e2e_runs_root=run_layout["e2e_runs_root"],
    )
    assert resolved.orchestration_dir is None
    assert resolved.main_session_dir is not None
    assert resolved.worktree_session_dirs  # still populated

    captured = capsys.readouterr()
    assert "orchestration dir missing" in captured.err


def test_no_sessions_at_all_raises(tmp_path):
    claude_root = tmp_path / ".claude" / "projects"
    claude_root.mkdir(parents=True)
    e2e_root = tmp_path / "e2e-runs"
    e2e_root.mkdir(parents=True)

    with pytest.raises(NoSessionDirsError):
        resolve_run(
            "nonexistent-run",
            claude_projects_root=claude_root,
            e2e_runs_root=e2e_root,
        )


def test_iter_all_session_dirs_yields_main_first(run_layout):
    resolved = resolve_run(
        run_layout["run_id"],
        claude_projects_root=run_layout["claude_projects_root"],
        e2e_runs_root=run_layout["e2e_runs_root"],
    )
    pairs = resolved.iter_all_session_dirs()
    assert pairs[0][0] == "main"
    changes = [c for c, _ in pairs]
    assert changes[1:] == sorted(changes[1:])  # worktrees in sorted order
