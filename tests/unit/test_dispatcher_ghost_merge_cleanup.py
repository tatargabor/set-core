"""Regression tests for the ghost-merge bug discovered in craftbrew-run-20260421-0025.

When `recover_orphaned_changes` resets a crashed `dispatched` change back to
`pending`, it must also clean up the stale `change/<name>` branch + worktree
that the crashed dispatch left behind. Otherwise the next dispatch cycle's
`_unique_worktree_name` generates a `-N` suffix, the agent commits to
`change/<name>-N`, and the merger's hardcoded `change/<name>` lookup hits an
empty sibling branch and short-circuits to "already merged" — a ghost merge
with zero diff that silently discards the agent's work.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from set_orch.dispatcher import recover_orphaned_changes


def _git(*args, cwd):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False,
    )


@pytest.fixture
def repo(tmp_path):
    """Real git repo with one commit on `main`."""
    _git("init", cwd=tmp_path)
    _git("checkout", "-b", "main", cwd=tmp_path)
    (tmp_path / "seed.txt").write_text("seed\n")
    _git("add", "-A", cwd=tmp_path)
    _git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init", cwd=tmp_path)
    return tmp_path


def _write_state(state_path: Path, change: dict) -> None:
    state = {
        "plan_version": 1,
        "brief_hash": "t",
        "status": "running",
        "created_at": "2026-04-21T00:00:00",
        "changes": [change],
        "merge_queue": [],
        "checkpoints": [],
        "changes_since_checkpoint": 0,
    }
    state_path.write_text(json.dumps(state))


def _base_change(name: str) -> dict:
    return {
        "name": name,
        "scope": "scope",
        "complexity": "M",
        "change_type": "feature",
        "depends_on": [],
        "status": "dispatched",
        "worktree_path": None,  # crash before state update
        "ralph_pid": None,
        "tokens_used": 0, "tokens_used_prev": 0,
        "input_tokens": 0, "output_tokens": 0,
        "cache_read_tokens": 0, "cache_create_tokens": 0,
        "input_tokens_prev": 0, "output_tokens_prev": 0,
        "cache_read_tokens_prev": 0, "cache_create_tokens_prev": 0,
        "verify_retry_count": 0, "redispatch_count": 0, "merge_retry_count": 0,
    }


def _seed_stale_worktree(repo: Path, change_name: str, commits_ahead: int) -> Path:
    """Create a `change/<name>` branch + worktree dir mirroring the crashed-dispatch state.

    Returns the worktree path.
    """
    branch = f"change/{change_name}"
    wt_path = repo.parent / f"{repo.name}-wt-{change_name}"
    r = _git("worktree", "add", "-b", branch, str(wt_path), "main", cwd=repo)
    assert r.returncode == 0, f"worktree add failed: {r.stderr}"

    for i in range(commits_ahead):
        (wt_path / f"extra-{i}.txt").write_text(f"extra {i}\n")
        _git("add", "-A", cwd=wt_path)
        _git("-c", "user.email=t@t", "-c", "user.name=t",
             "commit", "-m", f"agent commit {i}", cwd=wt_path)

    return wt_path


def _branch_exists(repo: Path, branch: str) -> bool:
    return _git("rev-parse", "--verify", branch, cwd=repo).returncode == 0


class TestGhostMergeCleanup:
    def test_empty_stale_branch_is_removed(self, repo, monkeypatch):
        """The pathological scenario from craftbrew-run-20260421-0025.

        Dispatch crashed after `set-new` created the worktree+branch but
        before state.worktree_path was updated. Recovery must clear the
        stale branch + worktree so the next dispatch reuses the clean
        `change/<name>` name instead of generating `-2`.
        """
        name = "email-dispatch-library"
        wt_path = _seed_stale_worktree(repo, name, commits_ahead=0)
        state_path = repo / "orchestration-state.json"
        _write_state(state_path, _base_change(name))

        # recover_orphaned_changes uses os.getcwd() internally for some git
        # calls; chdir to the repo to keep the test hermetic.
        monkeypatch.chdir(repo)
        count = recover_orphaned_changes(str(state_path))

        assert count == 1, "change should have been recovered"

        with state_path.open() as f:
            st = json.load(f)
        assert st["changes"][0]["status"] == "pending"

        assert not _branch_exists(repo, f"change/{name}"), \
            "stale empty branch must be deleted after recovery"
        assert not wt_path.exists(), \
            "stale worktree dir must be removed after recovery"

        # `git worktree list` should no longer show the stale registration
        r = _git("worktree", "list", "--porcelain", cwd=repo)
        assert f"-wt-{name}" not in r.stdout, \
            "stale worktree registration must be pruned"

    def test_branch_with_uncommitted_work_preserved(self, repo, monkeypatch):
        """If the stale branch has commits ahead of main, preserve it.

        Rationale: a redispatch cycle is the legitimate producer of this
        state — the engine expects the `-N` suffix path to pick it up.
        We only clean up when the branch is provably empty (0 ahead).
        """
        name = "partial-work"
        wt_path = _seed_stale_worktree(repo, name, commits_ahead=1)
        state_path = repo / "orchestration-state.json"
        _write_state(state_path, _base_change(name))

        monkeypatch.chdir(repo)
        count = recover_orphaned_changes(str(state_path))

        assert count == 1
        with state_path.open() as f:
            st = json.load(f)
        assert st["changes"][0]["status"] == "pending"

        # Branch MUST still exist — holds committed agent work
        assert _branch_exists(repo, f"change/{name}"), \
            "branch with commits ahead must be preserved"
        assert wt_path.exists(), "worktree with committed work must be preserved"
