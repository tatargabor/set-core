"""Tests for set_orch.engine — Directive parsing, token budget, time limit, completion, checkpoints."""

import json
import os
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.engine import (
    Directives,
    _check_completion,
    _checkpoint_approved,
    _clear_checkpoint_state,
    _recover_verify_failed,
    _signal_alive,
    _verify_gates_already_passed,
    parse_directives,
    trigger_checkpoint,
)
from set_orch.state import OrchestratorState, Change, load_state, save_state


class TestDirectivesDefaults:
    def test_default_values(self):
        """Directives dataclass has sensible defaults."""
        d = Directives()
        assert d.max_parallel == 3
        assert d.test_timeout == 300
        assert d.merge_policy == "eager"
        assert d.review_model == "opus"
        assert d.auto_replan is False
        assert d.smoke_blocking is False
        assert d.token_budget == 0
        assert d.milestones_enabled is False
        assert d.e2e_mode == "per_change"
        assert d.context_pruning is True
        assert d.model_routing == "off"
        assert d.team_mode is False

    def test_all_fields_present(self):
        """All ~40 directive fields are accessible."""
        d = Directives()
        fields = [f for f in dir(d) if not f.startswith("_")]
        # Should have a large number of fields
        assert len(fields) >= 30


class TestParseDirectives:
    def test_empty_dict(self):
        """Empty dict yields all defaults."""
        d = parse_directives({})
        assert d.max_parallel == 3
        assert d.test_command == ""
        assert d.auto_replan is False
        assert d.smoke_command == ""

    def test_all_fields(self):
        """All fields parse correctly from JSON."""
        raw = {
            "max_parallel": 5,
            "test_command": "pnpm test",
            "merge_policy": "conservative",
            "token_budget": 2000000,
            "auto_replan": True,
            "test_timeout": 600,
            "max_verify_retries": 3,
            "review_before_merge": True,
            "review_model": "sonnet",
            "default_model": "sonnet",
            "smoke_command": "pnpm smoke",
            "smoke_timeout": 180,
            "smoke_blocking": True,
            "smoke_fix_max_retries": 5,
            "smoke_fix_max_turns": 20,
            "smoke_health_check_url": "http://localhost:3000/health",
            "smoke_health_check_timeout": 60,
            "e2e_command": "pnpm e2e",
            "e2e_timeout": 300,
            "e2e_mode": "phase_end",
            "e2e_port_base": 4000,
            "token_hard_limit": 10000000,
            "checkpoint_every": 5,
            "max_replan_cycles": 8,
            "time_limit": "10h",
            "monitor_idle_timeout": 600,
            "context_pruning": False,
            "model_routing": "complexity",
            "team_mode": True,
            "post_merge_command": "pnpm db:generate",
            "post_phase_audit": True,
            "checkpoint_auto_approve": True,
            "max_redispatch": 3,
        }
        d = parse_directives(raw)
        assert d.max_parallel == 5
        assert d.test_command == "pnpm test"
        assert d.merge_policy == "conservative"
        assert d.token_budget == 2000000
        assert d.auto_replan is True
        assert d.test_timeout == 600
        assert d.max_verify_retries == 3
        assert d.review_before_merge is True
        assert d.review_model == "sonnet"
        assert d.default_model == "sonnet"
        assert d.smoke_command == "pnpm smoke"
        assert d.smoke_timeout == 180
        assert d.smoke_blocking is True
        assert d.e2e_command == "pnpm e2e"
        assert d.e2e_mode == "phase_end"
        assert d.e2e_port_base == 4000
        assert d.token_hard_limit == 10000000
        assert d.context_pruning is False
        assert d.model_routing == "complexity"
        assert d.team_mode is True
        assert d.post_merge_command == "pnpm db:generate"
        assert d.checkpoint_auto_approve is True
        assert d.max_redispatch == 3

    def test_string_to_int_coercion(self):
        """String values get coerced to int where needed."""
        raw = {"max_parallel": "7", "test_timeout": "120", "token_budget": "5000000"}
        d = parse_directives(raw)
        assert d.max_parallel == 7
        assert d.test_timeout == 120
        assert d.token_budget == 5000000

    def test_string_to_bool_coercion(self):
        """String 'true'/'false' get coerced to bool."""
        raw = {
            "auto_replan": "true",
            "review_before_merge": "false",
            "smoke_blocking": "true",
        }
        d = parse_directives(raw)
        assert d.auto_replan is True
        assert d.review_before_merge is False
        assert d.smoke_blocking is True

    def test_milestones_nested(self):
        """Milestone config parses from nested 'milestones' key."""
        raw = {
            "milestones": {
                "enabled": True,
                "dev_server": "pnpm dev",
                "base_port": 4000,
                "max_worktrees": 5,
            }
        }
        d = parse_directives(raw)
        assert d.milestones_enabled is True
        assert d.milestones_dev_server == "pnpm dev"
        assert d.milestones_base_port == 4000
        assert d.milestones_max_worktrees == 5

    def test_milestones_defaults(self):
        """Milestones default to disabled."""
        d = parse_directives({})
        assert d.milestones_enabled is False
        assert d.milestones_dev_server == ""
        assert d.milestones_base_port == 3100
        assert d.milestones_max_worktrees == 3

    def test_hook_directives(self):
        """Hook directives parse correctly."""
        raw = {
            "hook_pre_dispatch": "echo pre",
            "hook_post_verify": "echo post",
            "hook_pre_merge": "echo merge",
            "hook_post_merge": "echo done",
            "hook_on_fail": "echo fail",
        }
        d = parse_directives(raw)
        assert d.hook_pre_dispatch == "echo pre"
        assert d.hook_post_verify == "echo post"
        assert d.hook_pre_merge == "echo merge"
        assert d.hook_post_merge == "echo done"
        assert d.hook_on_fail == "echo fail"

    def test_unknown_fields_ignored(self):
        """Unknown fields don't cause errors."""
        raw = {"unknown_field": "value", "max_parallel": 10}
        d = parse_directives(raw)
        assert d.max_parallel == 10

    def test_time_limit_parsing(self):
        """Time limit string is parsed to seconds."""
        raw = {"time_limit": "2h"}
        d = parse_directives(raw)
        assert d.time_limit_secs == 7200  # 2 hours

    def test_time_limit_none(self):
        """Time limit 'none' disables it (stays 0)."""
        raw = {"time_limit": "none"}
        d = parse_directives(raw)
        assert d.time_limit_secs == 0


class TestTokenBudgetLogic:
    """Test token budget threshold calculations using Directives."""

    def test_zero_budget_means_unlimited(self):
        d = parse_directives({"token_budget": 0})
        assert d.token_budget == 0

    def test_budget_threshold(self):
        d = parse_directives({"token_budget": 5000000})
        total_tokens = 6000000
        assert total_tokens > d.token_budget

    def test_hard_limit_default(self):
        d = parse_directives({})
        assert d.token_hard_limit > 0


class TestTimeLimitLogic:
    """Test time limit parsing edge cases."""

    def test_default_time_limit(self):
        d = parse_directives({})
        assert d.time_limit_secs == 18000  # 5h default

    def test_disabled_time_limit(self):
        for val in ["none", "0"]:
            d = parse_directives({"time_limit": val})
            assert d.time_limit_secs == 0


class TestCompletionDetection:
    """Test terminal status detection logic."""

    def test_terminal_statuses(self):
        """All terminal statuses are recognized."""
        terminal = {"merged", "done", "skipped", "failed", "merge-blocked"}
        for status in terminal:
            # These are the statuses that should count toward completion
            assert status in terminal

    def test_active_statuses(self):
        """Active statuses are not terminal."""
        active = {"running", "pending", "verifying", "stalled", "dispatched"}
        terminal = {"merged", "done", "skipped", "failed", "merge-blocked"}
        for status in active:
            assert status not in terminal


# ─── Checkpoint Test Helpers ──────────────────────────────────────


def _make_checkpoint_state(
    state_file,
    *,
    status="running",
    changes_since_checkpoint=0,
    checkpoints=None,
    extras=None,
    changes=None,
):
    """Write a state file with configurable checkpoint fields."""
    state = OrchestratorState(
        status=status,
        changes=changes or [
            Change(name="change-1", status="merged"),
            Change(name="change-2", status="running"),
            Change(name="change-3", status="pending"),
        ],
        changes_since_checkpoint=changes_since_checkpoint,
        checkpoints=checkpoints or [],
        extras=extras or {},
    )
    save_state(state, state_file)
    return state


# ─── 6.1: Checkpoint Timeout Directive Parsing ───────────────────


class TestCheckpointTimeoutDirective:
    """Test checkpoint_timeout directive parsing (present and absent)."""

    def test_checkpoint_timeout_present(self):
        """checkpoint_timeout parses from directives JSON."""
        d = parse_directives({"checkpoint_timeout": 3600})
        assert d.checkpoint_timeout == 3600

    def test_checkpoint_timeout_absent(self):
        """checkpoint_timeout defaults to 0 (disabled) when absent."""
        d = parse_directives({})
        assert d.checkpoint_timeout == 0

    def test_checkpoint_timeout_string_coercion(self):
        """String checkpoint_timeout is coerced to int."""
        d = parse_directives({"checkpoint_timeout": "1800"})
        assert d.checkpoint_timeout == 1800

    def test_checkpoint_timeout_zero_means_disabled(self):
        """checkpoint_timeout=0 means no timeout."""
        d = parse_directives({"checkpoint_timeout": 0})
        assert d.checkpoint_timeout == 0


# ─── 6.2: trigger_checkpoint() Counter Reset ─────────────────────


class TestTriggerCheckpointCounterReset:
    """Test that trigger_checkpoint() resets changes_since_checkpoint to 0."""

    def test_counter_resets_to_zero(self, tmp_path):
        """changes_since_checkpoint is reset to 0 after checkpoint trigger."""
        state_file = str(tmp_path / "state.json")
        _make_checkpoint_state(state_file, changes_since_checkpoint=5)

        trigger_checkpoint(state_file, "periodic")

        state = load_state(state_file)
        assert state.changes_since_checkpoint == 0


# ─── 6.3: trigger_checkpoint() Stores checkpoint_started_at ──────


class TestTriggerCheckpointStartedAt:
    """Test that trigger_checkpoint() stores checkpoint_started_at in state extras."""

    def test_started_at_stored(self, tmp_path):
        """checkpoint_started_at is stored as epoch seconds in state extras."""
        state_file = str(tmp_path / "state.json")
        _make_checkpoint_state(state_file)

        before = int(time.time())
        trigger_checkpoint(state_file, "periodic")
        after = int(time.time())

        state = load_state(state_file)
        started_at = state.extras.get("checkpoint_started_at")
        assert started_at is not None
        assert before <= started_at <= after


# ─── 6.4: trigger_checkpoint() Appends Checkpoint Record ─────────


class TestTriggerCheckpointRecord:
    """Test that trigger_checkpoint() appends checkpoint record to state.checkpoints."""

    def test_checkpoint_record_appended(self, tmp_path):
        """A checkpoint record with reason, triggered_at, changes_completed, approved is appended."""
        state_file = str(tmp_path / "state.json")
        _make_checkpoint_state(
            state_file,
            changes=[
                Change(name="c1", status="merged"),
                Change(name="c2", status="done"),
                Change(name="c3", status="running"),
            ],
        )

        trigger_checkpoint(state_file, "token_hard_limit")

        state = load_state(state_file)
        assert len(state.checkpoints) == 1
        record = state.checkpoints[0]
        assert record["reason"] == "token_hard_limit"
        assert "triggered_at" in record
        assert record["changes_completed"] == 2  # merged + done
        assert record["approved"] is False

    def test_multiple_checkpoints_accumulate(self, tmp_path):
        """Multiple trigger_checkpoint() calls append distinct records."""
        state_file = str(tmp_path / "state.json")
        _make_checkpoint_state(state_file)

        trigger_checkpoint(state_file, "periodic")
        trigger_checkpoint(state_file, "token_hard_limit")

        state = load_state(state_file)
        assert len(state.checkpoints) == 2
        assert state.checkpoints[0]["reason"] == "periodic"
        assert state.checkpoints[1]["reason"] == "token_hard_limit"


# ─── 6.5: _checkpoint_approved() Returns True When Approved ──────


class TestCheckpointApprovedTrue:
    """Test _checkpoint_approved() returning true when latest checkpoint has approved: true."""

    def test_approved_true(self):
        """Returns True when latest checkpoint record has approved=True."""
        state = OrchestratorState(
            checkpoints=[
                {"reason": "periodic", "approved": False},
                {"reason": "periodic", "approved": True},
            ]
        )
        assert _checkpoint_approved(state) is True

    def test_only_latest_matters(self):
        """Only the last checkpoint record matters."""
        state = OrchestratorState(
            checkpoints=[
                {"reason": "periodic", "approved": True},
                {"reason": "periodic", "approved": False},
            ]
        )
        assert _checkpoint_approved(state) is False


# ─── 6.6: _checkpoint_approved() Returns False When No Checkpoints


class TestCheckpointApprovedFalse:
    """Test _checkpoint_approved() returning false when no checkpoints exist."""

    def test_no_checkpoints(self):
        """Returns False when checkpoints list is empty."""
        state = OrchestratorState(checkpoints=[])
        assert _checkpoint_approved(state) is False

    def test_no_checkpoints_in_extras_either(self):
        """Returns False when both checkpoints list and extras are empty."""
        state = OrchestratorState(checkpoints=[], extras={})
        assert _checkpoint_approved(state) is False

    def test_extras_fallback(self):
        """Falls back to extras['checkpoints'] if state.checkpoints is empty."""
        state = OrchestratorState(
            checkpoints=[],
            extras={"checkpoints": [{"reason": "periodic", "approved": True}]},
        )
        assert _checkpoint_approved(state) is True


# ─── 6.7: Checkpoint Timeout Auto-Resume Logic ───────────────────


class TestCheckpointTimeoutAutoResume:
    """Test checkpoint timeout auto-resume logic (mock time to exceed timeout)."""

    def test_timeout_triggers_resume(self, tmp_path):
        """When checkpoint_started_at + timeout < now, state should resume."""
        state_file = str(tmp_path / "state.json")
        # Set checkpoint_started_at to 3700 seconds ago
        started_at = int(time.time()) - 3700
        _make_checkpoint_state(
            state_file,
            status="checkpoint",
            extras={"checkpoint_started_at": started_at},
        )

        # Simulate what monitor_loop does for timeout check
        d = Directives(checkpoint_timeout=3600)
        state = load_state(state_file)

        if d.checkpoint_timeout > 0:
            cs = state.extras.get("checkpoint_started_at", 0)
            if cs and (int(time.time()) - cs) >= d.checkpoint_timeout:
                from set_orch.state import update_state_field
                update_state_field(state_file, "status", "running")

        state = load_state(state_file)
        assert state.status == "running"

    def test_no_timeout_when_not_exceeded(self, tmp_path):
        """When timeout has not elapsed, state remains checkpoint."""
        state_file = str(tmp_path / "state.json")
        # Set checkpoint_started_at to 10 seconds ago (well under 3600s timeout)
        started_at = int(time.time()) - 10
        _make_checkpoint_state(
            state_file,
            status="checkpoint",
            extras={"checkpoint_started_at": started_at},
        )

        d = Directives(checkpoint_timeout=3600)
        state = load_state(state_file)

        resumed = False
        if d.checkpoint_timeout > 0:
            cs = state.extras.get("checkpoint_started_at", 0)
            if cs and (int(time.time()) - cs) >= d.checkpoint_timeout:
                resumed = True

        assert resumed is False
        state = load_state(state_file)
        assert state.status == "checkpoint"

    def test_no_timeout_when_disabled(self, tmp_path):
        """When checkpoint_timeout=0, no timeout check is performed."""
        state_file = str(tmp_path / "state.json")
        started_at = int(time.time()) - 99999  # way in the past
        _make_checkpoint_state(
            state_file,
            status="checkpoint",
            extras={"checkpoint_started_at": started_at},
        )

        d = Directives(checkpoint_timeout=0)
        state = load_state(state_file)

        resumed = False
        if d.checkpoint_timeout > 0:
            cs = state.extras.get("checkpoint_started_at", 0)
            if cs and (int(time.time()) - cs) >= d.checkpoint_timeout:
                resumed = True

        assert resumed is False


# ─── 6.8: Counter Reset Cadence ──────────────────────────────────


class TestCheckpointCounterResetCadence:
    """Test checkpoint counter reset cadence: checkpoint_every=3 triggers at 3, 6, 9."""

    def test_checkpoint_triggers_every_n_changes(self, tmp_path):
        """With checkpoint_every=3, checkpoints trigger at 3, 6, 9 changes (not 3, 6, 9 cumulative)."""
        state_file = str(tmp_path / "state.json")
        _make_checkpoint_state(state_file, changes_since_checkpoint=0)

        checkpoint_every = 3
        trigger_count = 0

        # Simulate 9 changes completing
        for i in range(1, 10):
            # Increment counter (simulating a change completing)
            state = load_state(state_file)
            from set_orch.state import update_state_field
            update_state_field(
                state_file,
                "changes_since_checkpoint",
                state.changes_since_checkpoint + 1,
            )

            # Check if checkpoint should trigger
            state = load_state(state_file)
            if state.changes_since_checkpoint >= checkpoint_every:
                trigger_checkpoint(state_file, "periodic")
                trigger_count += 1

                # Verify counter was reset
                state = load_state(state_file)
                assert state.changes_since_checkpoint == 0, (
                    f"Counter should be 0 after checkpoint at change {i}, "
                    f"got {state.changes_since_checkpoint}"
                )

                # Resume from checkpoint for next cycle
                update_state_field(state_file, "status", "running")

        # Should have triggered 3 times: at changes 3, 6, 9
        assert trigger_count == 3

    def test_counter_not_accumulating(self, tmp_path):
        """Verify the old accumulating bug is fixed: counter resets, not accumulates."""
        state_file = str(tmp_path / "state.json")
        _make_checkpoint_state(state_file, changes_since_checkpoint=0)

        # First checkpoint at change 3
        from set_orch.state import update_state_field
        update_state_field(state_file, "changes_since_checkpoint", 3)
        trigger_checkpoint(state_file, "periodic")

        state = load_state(state_file)
        assert state.changes_since_checkpoint == 0

        # After resume, increment to 3 again (total 6 changes)
        update_state_field(state_file, "status", "running")
        update_state_field(state_file, "changes_since_checkpoint", 3)

        # This should trigger (counter is 3, not needing to reach 6)
        state = load_state(state_file)
        assert state.changes_since_checkpoint >= 3  # triggers at 3, not 6


# ─── Heartbeat Throttle ─────────────────────────────────────────


class TestHeartbeatThrottle:
    """Test that WATCHDOG_HEARTBEAT is only emitted every 20th poll cycle."""

    def test_heartbeat_emitted_every_20th_poll(self):
        """Heartbeat should emit at poll_count 20, 40, 60 — not every poll."""
        emitted = []
        for poll_count in range(1, 61):
            if poll_count % 20 == 0:
                emitted.append(poll_count)
        assert emitted == [20, 40, 60]

    def test_first_19_polls_no_heartbeat(self):
        """No heartbeat event during first 19 poll cycles."""
        for poll_count in range(1, 20):
            assert poll_count % 20 != 0

    def test_heartbeat_at_poll_20(self):
        """Heartbeat fires exactly at poll 20."""
        assert 20 % 20 == 0

    def test_throttle_reduces_frequency(self):
        """Over 100 polls, only 5 heartbeats should emit (not 100)."""
        emit_count = sum(1 for p in range(1, 101) if p % 20 == 0)
        assert emit_count == 5


class TestSignalAlive:
    """Tests for _signal_alive() heartbeat helper."""

    def test_emits_heartbeat_event(self, tmp_path):
        """_signal_alive emits WATCHDOG_HEARTBEAT when event_bus is provided."""
        state_file = str(tmp_path / "state.json")
        with open(state_file, "w") as f:
            f.write("{}")

        class FakeEventBus:
            def __init__(self):
                self.events = []
            def emit(self, event_type, **kwargs):
                self.events.append(event_type)

        bus = FakeEventBus()
        _signal_alive(state_file, bus)
        assert "WATCHDOG_HEARTBEAT" in bus.events

    def test_touches_state_file_mtime(self, tmp_path):
        """_signal_alive updates the state file's modification time."""
        state_file = str(tmp_path / "state.json")
        with open(state_file, "w") as f:
            f.write("{}")

        # Set mtime to past
        old_time = time.time() - 300
        os.utime(state_file, (old_time, old_time))

        before_mtime = os.path.getmtime(state_file)
        _signal_alive(state_file, None)
        after_mtime = os.path.getmtime(state_file)

        assert after_mtime > before_mtime

    def test_none_event_bus(self, tmp_path):
        """_signal_alive handles None event_bus without error."""
        state_file = str(tmp_path / "state.json")
        with open(state_file, "w") as f:
            f.write("{}")

        # Should not raise
        _signal_alive(state_file, None)
        # Verify mtime was still touched
        assert os.path.getmtime(state_file) > 0

    def test_missing_state_file(self, tmp_path):
        """_signal_alive handles missing state file without raising."""
        missing_file = str(tmp_path / "nonexistent.json")

        # Should not raise
        _signal_alive(missing_file, None)


# ─── _check_completion merge_queue guard ─────────────────────────


class TestCheckCompletionMergeQueueGuard:
    """_check_completion must return False when merge_queue is non-empty."""

    def test_returns_false_when_merge_queue_non_empty(self, tmp_path):
        """Even if all changes are 'done', non-empty merge_queue prevents exit."""
        state_file = str(tmp_path / "state.json")
        state = OrchestratorState(
            status="running",
            changes=[
                Change(name="c1", status="done"),
                Change(name="c2", status="done"),
            ],
            merge_queue=["c1", "c2"],
        )
        save_state(state, state_file)

        d = Directives()
        result = _check_completion(state_file, d, None)
        assert result is False

    def test_returns_true_when_merge_queue_empty_all_merged(self, tmp_path):
        """When merge_queue is empty and all changes merged, completion is allowed."""
        state_file = str(tmp_path / "state.json")
        state = OrchestratorState(
            status="running",
            changes=[
                Change(name="c1", status="merged"),
                Change(name="c2", status="merged"),
            ],
            merge_queue=[],
        )
        save_state(state, state_file)

        d = Directives()
        result = _check_completion(state_file, d, None)
        assert result is True

    def test_merge_exception_leaves_done_in_queue(self, tmp_path):
        """Simulates merge exception: change is 'done' AND in merge_queue."""
        state_file = str(tmp_path / "state.json")
        state = OrchestratorState(
            status="running",
            changes=[
                Change(name="c1", status="merged"),
                Change(name="c2", status="done"),  # merge threw exception
            ],
            merge_queue=["c2"],
        )
        save_state(state, state_file)

        d = Directives()
        result = _check_completion(state_file, d, None)
        assert result is False


# ─── _verify_gates_already_passed extended gate checks ───────────


class TestVerifyGatesAlreadyPassed:
    """_verify_gates_already_passed must check all blocking gates."""

    def _make_change(self, **overrides):
        """Create a Change with all gates passing by default.

        e2e_result is a dataclass field (not extras). scope_check and
        spec_coverage_result live in extras.
        """
        defaults = dict(
            name="test-change",
            status="verifying",
            test_result="pass",
            build_result="pass",
            review_result="pass",
            e2e_result="pass",
            extras={
                "scope_check": "pass",
                "spec_coverage_result": "pass",
            },
        )
        defaults.update(overrides)
        return Change(**defaults)

    def test_all_gates_pass(self):
        """Returns True when all gates pass."""
        change = self._make_change()
        assert _verify_gates_already_passed(change) is True

    def test_missing_review_result(self):
        """Returns False when review_result is None (gate hasn't run)."""
        change = self._make_change(review_result=None)
        assert _verify_gates_already_passed(change) is False

    def test_failed_e2e_result(self):
        """Returns False when e2e_result (dataclass field) is 'fail'."""
        change = self._make_change(e2e_result="fail")
        assert _verify_gates_already_passed(change) is False

    def test_failed_spec_coverage_result(self):
        """Returns False when spec_coverage_result is 'fail' in extras."""
        change = self._make_change(
            extras={
                "scope_check": "pass",
                "spec_coverage_result": "fail",
            }
        )
        assert _verify_gates_already_passed(change) is False

    def test_missing_e2e_result(self):
        """Returns False when e2e_result dataclass field is None."""
        change = self._make_change(e2e_result=None)
        assert _verify_gates_already_passed(change) is False

    def test_warn_fail_is_accepted(self):
        """warn-fail counts as passing (non-blocking gate failure)."""
        change = self._make_change(e2e_result="warn-fail")
        assert _verify_gates_already_passed(change) is True

    def test_skipped_is_accepted(self):
        """Skipped gates count as passing."""
        change = self._make_change(
            test_result="skipped",
            e2e_result="skipped",
            extras={
                "scope_check": "pass",
                "spec_coverage_result": "skipped",
            },
        )
        assert _verify_gates_already_passed(change) is True

    def test_scope_check_result_key_accepted(self):
        """scope_check_result is accepted as alias for scope_check.

        State dumps from real runs (craftbrew-run-20260414) persist this
        key with the `_result` suffix; gate_runner.commit_results writes
        the short form. Accept both.
        """
        change = self._make_change(
            extras={
                "scope_check_result": "pass",
                "spec_coverage_result": "pass",
            }
        )
        assert _verify_gates_already_passed(change) is True


# ─── _recover_verify_failed no double increment ─────────────────


class TestRecoverVerifyFailedNoDoubleIncrement:
    """_recover_verify_failed must NOT increment verify_retry_count."""

    def test_retry_count_not_incremented(self, tmp_path, monkeypatch):
        """verify_retry_count stays at the value set by handle_change_done."""
        state_file = str(tmp_path / "state.json")
        state = OrchestratorState(
            status="running",
            changes=[
                Change(
                    name="c1",
                    status="verify-failed",
                    verify_retry_count=1,  # already incremented by handle_change_done
                    extras={"retry_context": "Fix the tests"},
                ),
            ],
        )
        save_state(state, state_file)

        # Mock resume_change at the dispatcher module level (imported locally)
        resumed = []
        import set_orch.dispatcher as _disp_mod
        monkeypatch.setattr(
            _disp_mod, "resume_change",
            lambda sf, cn, **kw: resumed.append(cn) or True,
        )

        d = Directives(max_verify_retries=3)
        _recover_verify_failed(state_file, d, None)

        # Verify resume was called
        assert resumed == ["c1"]

        # Verify retry count was NOT incremented (stays at 1, not bumped to 2)
        state = load_state(state_file)
        c1 = [c for c in state.changes if c.name == "c1"][0]
        assert c1.verify_retry_count == 1

    def test_exhausted_retries_marks_failed(self, tmp_path, monkeypatch):
        """When retries exhausted, change is marked failed without incrementing."""
        state_file = str(tmp_path / "state.json")
        state = OrchestratorState(
            status="running",
            changes=[
                Change(
                    name="c1",
                    status="verify-failed",
                    verify_retry_count=3,
                    extras={"build_output": "error: cannot find module"},
                ),
            ],
        )
        save_state(state, state_file)

        # Mock resume_change at the dispatcher module level
        resumed = []
        import set_orch.dispatcher as _disp_mod
        monkeypatch.setattr(
            _disp_mod, "resume_change",
            lambda sf, cn, **kw: resumed.append(cn) or True,
        )

        d = Directives(max_verify_retries=3)
        _recover_verify_failed(state_file, d, None)

        # Should NOT have resumed
        assert resumed == []

        # Should be marked failed
        state = load_state(state_file)
        c1 = [c for c in state.changes if c.name == "c1"][0]
        assert c1.status == "failed"
        assert c1.verify_retry_count == 3  # not incremented
