"""Integration tests for orchestration state machine.

Tests dependency cascade, state persistence, and dispatch logic
using real state files (no mocks).

Bug patterns tested:
- C1: Dependency cascade deadlock (Run #2 Bug #16, Run #4, Run #5 Bug #26)
- C3: State save/load round-trip (Run #19 Bug #50)
- C7: Missing worktree recovery (Run #1, Run #3 Bug #19)
"""

import json

from lib.set_orch.state import (
    Change,
    OrchestratorState,
    cascade_failed_deps,
    deps_failed,
    deps_satisfied,
    load_state,
    save_state,
)

from tests.integration.helpers import change_dict


# ── C1: Dependency cascade ────────────────────────────────────────


class TestDependencyCascade:
    """Run #2 Bug #16, Run #4, Run #5 Bug #26:
    When dep fails, dependents stuck pending forever → orchestrator hangs.
    cascade_failed_deps() must propagate failure transitively.
    """

    def test_single_dep_fails_cascades(self, tmp_path, create_state_file, git_repo):
        """A fails → B (depends_on A) auto-cascades to failed."""
        repo = git_repo()
        sf = create_state_file(repo, changes=[
            change_dict("change-a", status="failed"),
            change_dict("change-b", status="pending", depends_on=["change-a"]),
        ])
        state = load_state(str(sf))
        cascaded = cascade_failed_deps(state)
        save_state(state, str(sf))

        assert cascaded == 1
        reloaded = load_state(str(sf))
        assert reloaded.changes[1].status == "failed"
        assert "dependency" in reloaded.changes[1].extras.get("failure_reason", "")

    def test_transitive_cascade(self, tmp_path, create_state_file, git_repo):
        """A fails → B (dep A) → C (dep B): both B and C should fail.
        Note: cascade_failed_deps() needs to be called iteratively
        because C depends on B, not A directly.
        """
        repo = git_repo()
        sf = create_state_file(repo, changes=[
            change_dict("change-a", status="failed"),
            change_dict("change-b", status="pending", depends_on=["change-a"]),
            change_dict("change-c", status="pending", depends_on=["change-b"]),
        ])
        state = load_state(str(sf))

        # First pass: A failed → B cascades
        cascade_failed_deps(state)
        # Second pass: B now failed → C cascades
        cascade_failed_deps(state)
        save_state(state, str(sf))

        reloaded = load_state(str(sf))
        assert reloaded.changes[0].status == "failed"  # A
        assert reloaded.changes[1].status == "failed"  # B
        assert reloaded.changes[2].status == "failed"  # C

    def test_partial_failure_unaffected(self, tmp_path, create_state_file, git_repo):
        """A fails, but C (no dep on A) should NOT be affected."""
        repo = git_repo()
        sf = create_state_file(repo, changes=[
            change_dict("change-a", status="failed"),
            change_dict("change-b", status="pending", depends_on=["change-a"]),
            change_dict("change-c", status="pending"),  # no dependency
        ])
        state = load_state(str(sf))
        cascade_failed_deps(state)
        save_state(state, str(sf))

        reloaded = load_state(str(sf))
        assert reloaded.changes[1].status == "failed"   # B cascaded
        assert reloaded.changes[2].status == "pending"   # C unaffected

    def test_only_pending_changes_cascade(self, tmp_path, create_state_file, git_repo):
        """Running or done changes should NOT cascade even if dep failed."""
        repo = git_repo()
        sf = create_state_file(repo, changes=[
            change_dict("change-a", status="failed"),
            change_dict("change-b", status="running", depends_on=["change-a"]),
        ])
        state = load_state(str(sf))
        cascaded = cascade_failed_deps(state)

        assert cascaded == 0
        assert state.changes[1].status == "running"


# ── Dependency satisfaction ────────────────────────────────────────


class TestDependencySatisfaction:
    """Dispatch logic: only dispatch when all deps are merged."""

    def test_dep_merged_satisfies(self, tmp_path, create_state_file, git_repo):
        repo = git_repo()
        sf = create_state_file(repo, changes=[
            change_dict("change-a", status="merged"),
            change_dict("change-b", status="pending", depends_on=["change-a"]),
        ])
        state = load_state(str(sf))
        assert deps_satisfied(state, "change-b") is True

    def test_dep_running_blocks(self, tmp_path, create_state_file, git_repo):
        repo = git_repo()
        sf = create_state_file(repo, changes=[
            change_dict("change-a", status="running"),
            change_dict("change-b", status="pending", depends_on=["change-a"]),
        ])
        state = load_state(str(sf))
        assert deps_satisfied(state, "change-b") is False

    def test_no_deps_always_satisfied(self, tmp_path, create_state_file, git_repo):
        repo = git_repo()
        sf = create_state_file(repo, changes=[
            change_dict("change-a", status="pending"),
        ])
        state = load_state(str(sf))
        assert deps_satisfied(state, "change-a") is True

    def test_deps_failed_detects(self, tmp_path, create_state_file, git_repo):
        repo = git_repo()
        sf = create_state_file(repo, changes=[
            change_dict("change-a", status="failed"),
            change_dict("change-b", status="pending", depends_on=["change-a"]),
        ])
        state = load_state(str(sf))
        assert deps_failed(state, "change-b") is True

    def test_merge_blocked_is_not_failure(self, tmp_path, create_state_file, git_repo):
        """merge-blocked is NOT a dep failure — the work is done, only merge is stuck."""
        repo = git_repo()
        sf = create_state_file(repo, changes=[
            change_dict("change-a", status="merge-blocked"),
            change_dict("change-b", status="pending", depends_on=["change-a"]),
        ])
        state = load_state(str(sf))
        assert deps_failed(state, "change-b") is False


# ── C3: State persistence round-trip ─────────────────────────────


class TestStatePersistence:
    """Run #19 Bug #50: state reconstruction loses merged status."""

    def test_full_round_trip(self, tmp_path):
        """All change fields survive save/load cycle."""
        state = OrchestratorState(
            plan_version=2,
            brief_hash="abc123",
            status="running",
            created_at="2026-01-01T00:00:00+00:00",
            changes=[
                Change(
                    name="test-change",
                    scope="Test scope",
                    status="merged",
                    tokens_used=50000,
                    input_tokens=30000,
                    output_tokens=20000,
                    verify_retry_count=2,
                    merge_retry_count=1,
                    started_at="2026-01-01T00:01:00+00:00",
                    completed_at="2026-01-01T00:10:00+00:00",
                    test_result="pass",
                    build_result="pass",
                    smoke_result="pass",
                ),
            ],
            merge_queue=["pending-change"],
            changes_since_checkpoint=3,
        )
        path = str(tmp_path / "state.json")
        save_state(state, path)
        loaded = load_state(path)

        assert loaded.plan_version == 2
        assert loaded.brief_hash == "abc123"
        assert loaded.status == "running"
        assert len(loaded.changes) == 1

        c = loaded.changes[0]
        assert c.name == "test-change"
        assert c.status == "merged"
        assert c.tokens_used == 50000
        assert c.verify_retry_count == 2
        assert c.merge_retry_count == 1
        assert c.started_at == "2026-01-01T00:01:00+00:00"
        assert c.completed_at == "2026-01-01T00:10:00+00:00"
        assert c.test_result == "pass"
        assert c.smoke_result == "pass"
        assert loaded.merge_queue == ["pending-change"]
        assert loaded.changes_since_checkpoint == 3

    def test_unknown_fields_preserved_via_extras(self, tmp_path):
        """Unknown JSON fields should survive round-trip in extras dict."""
        path = str(tmp_path / "state.json")
        raw = {
            "plan_version": 1,
            "changes": [{
                "name": "test",
                "status": "pending",
                "custom_field": "preserved",
                "agent_rebase_done": True,
            }],
            "unknown_top_level": 42,
        }
        (tmp_path / "state.json").write_text(json.dumps(raw))
        state = load_state(path)

        # Unknown fields in extras
        assert state.extras.get("unknown_top_level") == 42
        assert state.changes[0].extras.get("custom_field") == "preserved"
        assert state.changes[0].extras.get("agent_rebase_done") is True

        # Round-trip
        save_state(state, path)
        reloaded = load_state(path)
        assert reloaded.extras.get("unknown_top_level") == 42
        assert reloaded.changes[0].extras.get("custom_field") == "preserved"


# ── C7: Missing worktree recovery ─────────────────────────────────


class TestMissingWorktree:
    """Run #1, Run #3 Bug #19:
    Worktree deleted but state references it → crash instead of re-dispatch.
    """

    def test_missing_worktree_state_loads_fine(self, tmp_path, create_state_file, git_repo):
        """State with non-existent worktree_path loads without error."""
        repo = git_repo()
        sf = create_state_file(repo, changes=[
            change_dict(
                "change-a",
                status="running",
                worktree_path="/tmp/this-does-not-exist-12345",
            ),
        ])
        state = load_state(str(sf))
        assert state.changes[0].worktree_path == "/tmp/this-does-not-exist-12345"
        assert state.changes[0].status == "running"

    def test_missing_worktree_deps_still_work(self, tmp_path, create_state_file, git_repo):
        """Dependency checks work even when worktree_path is invalid."""
        repo = git_repo()
        sf = create_state_file(repo, changes=[
            change_dict("change-a", status="merged",
                         worktree_path="/tmp/deleted-wt"),
            change_dict("change-b", status="pending", depends_on=["change-a"]),
        ])
        state = load_state(str(sf))
        assert deps_satisfied(state, "change-b") is True
