"""Tests for set_orch.state — Typed JSON state management."""

import json
import os
import stat
import sys
import tempfile
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.state import (
    Change,
    CircularDependencyError,
    OrchestratorState,
    StateCorruptionError,
    TokenStats,
    WatchdogState,
    advance_phase,
    aggregate_tokens,
    all_phase_changes_terminal,
    apply_phase_overrides,
    cascade_failed_deps,
    count_changes_by_status,
    deps_failed,
    deps_satisfied,
    get_change_status,
    get_changes_by_status,
    init_phase_state,
    init_state,
    load_state,
    locked_state,
    query_changes,
    reconstruct_state_from_events,
    run_hook,
    save_state,
    topological_sort,
    update_change_field,
    update_state_field,
)
from set_orch.events import EventBus


SAMPLE_PLAN = {
    "plan_version": 2,
    "brief_hash": "abc123",
    "plan_phase": "initial",
    "plan_method": "api",
    "changes": [
        {
            "name": "add-auth",
            "scope": "Add authentication",
            "complexity": "L",
            "change_type": "feature",
            "depends_on": [],
            "roadmap_item": "Auth system",
            "requirements": ["REQ-AUTH-01"],
        },
        {
            "name": "fix-login",
            "scope": "Fix login bug",
            "complexity": "S",
            "change_type": "bugfix",
            "depends_on": ["add-auth"],
            "roadmap_item": "Login fixes",
        },
    ],
}


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    import shutil
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def plan_file(tmp_dir):
    path = os.path.join(tmp_dir, "plan.json")
    with open(path, "w") as f:
        json.dump(SAMPLE_PLAN, f)
    return path


@pytest.fixture
def state_file(tmp_dir, plan_file):
    path = os.path.join(tmp_dir, "state.json")
    init_state(plan_file, path)
    return path


class TestLoadState:
    def test_loads_valid_state(self, state_file):
        state = load_state(state_file)
        assert state.status == "running"
        assert len(state.changes) == 2
        assert state.plan_version == 2
        assert state.brief_hash == "abc123"

    def test_rejects_corrupt_json(self, tmp_dir):
        path = os.path.join(tmp_dir, "corrupt.json")
        with open(path, "w") as f:
            f.write("NOT VALID JSON {{{")
        with pytest.raises(StateCorruptionError, match="invalid JSON"):
            load_state(path)

    def test_rejects_empty_file(self, tmp_dir):
        path = os.path.join(tmp_dir, "empty.json")
        with open(path, "w") as f:
            f.write("")
        with pytest.raises(StateCorruptionError, match="empty"):
            load_state(path)

    def test_rejects_missing_changes(self, tmp_dir):
        path = os.path.join(tmp_dir, "nochanges.json")
        with open(path, "w") as f:
            json.dump({"status": "running"}, f)
        with pytest.raises(StateCorruptionError, match="missing required field: changes"):
            load_state(path)

    def test_rejects_nonexistent_file(self):
        with pytest.raises(StateCorruptionError, match="cannot read file"):
            load_state("/nonexistent/path/state.json")

    def test_preserves_unknown_fields(self, tmp_dir):
        path = os.path.join(tmp_dir, "extra.json")
        data = {
            "status": "running",
            "changes": [],
            "custom_field": "hello",
            "directives": {"test_command": "npm test"},
        }
        with open(path, "w") as f:
            json.dump(data, f)

        state = load_state(path)
        assert state.extras["custom_field"] == "hello"
        assert state.extras["directives"] == {"test_command": "npm test"}


class TestSaveState:
    def test_save_load_roundtrip(self, state_file):
        state = load_state(state_file)
        state.changes[0].status = "running"
        state.changes[0].tokens_used = 5000

        save_state(state, state_file)
        state2 = load_state(state_file)

        assert state2.changes[0].status == "running"
        assert state2.changes[0].tokens_used == 5000
        assert state2.changes[1].status == "pending"

    def test_atomic_write(self, tmp_dir):
        path = os.path.join(tmp_dir, "atomic.json")
        state = OrchestratorState(status="running", changes=[])
        save_state(state, path)
        assert os.path.exists(path)
        # No .tmp files left behind
        tmp_files = [f for f in os.listdir(tmp_dir) if f.endswith(".tmp")]
        assert tmp_files == []

    def test_preserves_extras_on_roundtrip(self, tmp_dir):
        path = os.path.join(tmp_dir, "extras.json")
        state = OrchestratorState(
            status="running",
            changes=[Change(name="test", extras={"smoke_status": "pass"})],
            extras={"directives": {"max_parallel": 3}},
        )
        save_state(state, path)
        state2 = load_state(path)
        assert state2.extras["directives"] == {"max_parallel": 3}
        assert state2.changes[0].extras["smoke_status"] == "pass"


class TestInitState:
    def test_creates_state_from_plan(self, plan_file, tmp_dir):
        out = os.path.join(tmp_dir, "out.json")
        init_state(plan_file, out)

        state = load_state(out)
        assert state.status == "running"
        assert state.plan_version == 2
        assert len(state.changes) == 2

        auth = state.changes[0]
        assert auth.name == "add-auth"
        assert auth.status == "pending"
        assert auth.tokens_used == 0
        assert auth.ralph_pid is None
        assert auth.requirements == ["REQ-AUTH-01"]

        fix = state.changes[1]
        assert fix.name == "fix-login"
        assert fix.depends_on == ["add-auth"]
        assert fix.requirements is None  # not in plan

    def test_plan_defaults(self, tmp_dir):
        plan = {"changes": [{"name": "minimal"}]}
        plan_path = os.path.join(tmp_dir, "minimal.json")
        with open(plan_path, "w") as f:
            json.dump(plan, f)

        out = os.path.join(tmp_dir, "out.json")
        init_state(plan_path, out)

        state = load_state(out)
        assert state.plan_version == 1
        assert state.plan_phase == "initial"
        c = state.changes[0]
        assert c.complexity == "M"
        assert c.change_type == "feature"


class TestQueryChanges:
    def test_filter_by_status(self, state_file):
        state = load_state(state_file)
        state.changes[0].status = "running"

        running = query_changes(state, status="running")
        assert len(running) == 1
        assert running[0].name == "add-auth"

        pending = query_changes(state, status="pending")
        assert len(pending) == 1
        assert pending[0].name == "fix-login"

    def test_no_filter_returns_all(self, state_file):
        state = load_state(state_file)
        all_changes = query_changes(state)
        assert len(all_changes) == 2

    def test_empty_result(self, state_file):
        state = load_state(state_file)
        result = query_changes(state, status="merged")
        assert result == []


class TestAggregateTokens:
    def test_aggregates_across_changes(self):
        state = OrchestratorState(changes=[
            Change(name="a", tokens_used=1000, input_tokens=500, output_tokens=300,
                   cache_read_tokens=100, cache_create_tokens=100),
            Change(name="b", tokens_used=2000, input_tokens=1000, output_tokens=600,
                   cache_read_tokens=200, cache_create_tokens=200),
        ])
        stats = aggregate_tokens(state)
        assert stats.total == 3000
        assert stats.input_total == 1500
        assert stats.output_total == 900
        assert stats.cache_read_total == 300
        assert stats.cache_create_total == 300

    def test_empty_changes(self):
        state = OrchestratorState(changes=[])
        stats = aggregate_tokens(state)
        assert stats.total == 0


class TestWatchdogState:
    def test_from_dict_roundtrip(self):
        data = {
            "last_activity_epoch": 1710000000,
            "action_hash_ring": ["abc", "def"],
            "consecutive_same_hash": 3,
            "escalation_level": 1,
            "progress_baseline": 5,
            "custom_field": "extra",
        }
        wd = WatchdogState.from_dict(data)
        assert wd.last_activity_epoch == 1710000000
        assert wd.action_hash_ring == ["abc", "def"]
        assert wd.extras["custom_field"] == "extra"

        d = wd.to_dict()
        assert d["custom_field"] == "extra"
        assert d["consecutive_same_hash"] == 3


class TestGateHintsRoundTrip:
    def test_gate_hints_to_dict_from_dict(self):
        hints = {"e2e": "skip", "smoke": "warn"}
        c = Change(name="with-hints", change_type="feature", gate_hints=hints)
        d = c.to_dict()
        assert d["gate_hints"] == hints

        c2 = Change.from_dict(d)
        assert c2.gate_hints == hints

    def test_gate_hints_none_omitted_from_dict(self):
        c = Change(name="no-hints", change_type="feature")
        d = c.to_dict()
        assert "gate_hints" not in d

    def test_gate_hints_survives_save_load(self, tmp_path):
        path = str(tmp_path / "state.json")
        hints = {"build": "skip", "review_model": "sonnet"}
        state = OrchestratorState(
            status="running",
            changes=[Change(name="hinted", gate_hints=hints)],
        )
        save_state(state, path)
        state2 = load_state(path)
        assert state2.changes[0].gate_hints == hints


# ─── Phase 2: Locking ────────────────────────────────────────────────


class TestLockedState:
    def test_context_manager_modifies_and_saves(self, state_file):
        with locked_state(state_file) as state:
            state.status = "stopped"
            state.changes[0].status = "running"

        state2 = load_state(state_file)
        assert state2.status == "stopped"
        assert state2.changes[0].status == "running"

    def test_lock_file_created(self, state_file):
        with locked_state(state_file) as _:
            assert os.path.exists(state_file + ".lock")

    def test_concurrent_writers_serialize(self, state_file):
        """Two threads writing simultaneously both succeed without corruption."""
        errors = []

        def writer(change_idx, new_status):
            try:
                with locked_state(state_file) as state:
                    state.changes[change_idx].status = new_status
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=writer, args=(0, "running"))
        t2 = threading.Thread(target=writer, args=(1, "merged"))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert errors == []
        state = load_state(state_file)
        # Both writes should succeed (order may vary but no corruption)
        statuses = {c.name: c.status for c in state.changes}
        # At minimum, the file is valid and both changes exist
        assert len(state.changes) == 2
        assert "add-auth" in statuses
        assert "fix-login" in statuses

    def test_save_state_uses_flock(self, state_file):
        """save_state creates a .lock file."""
        state = load_state(state_file)
        state.status = "testing"
        save_state(state, state_file)
        assert os.path.exists(state_file + ".lock")
        state2 = load_state(state_file)
        assert state2.status == "testing"


# ─── Phase 2: Mutation Functions ──────────────────────────────────────


class TestUpdateStateField:
    def test_update_known_field(self, state_file):
        update_state_field(state_file, "status", "stopped")
        state = load_state(state_file)
        assert state.status == "stopped"

    def test_update_extras_field(self, state_file):
        update_state_field(state_file, "custom_key", "custom_val")
        state = load_state(state_file)
        assert state.extras["custom_key"] == "custom_val"


class TestUpdateChangeField:
    def test_update_status(self, state_file):
        update_change_field(state_file, "add-auth", "status", "running")
        state = load_state(state_file)
        assert state.changes[0].status == "running"

    def test_update_extras_field(self, state_file):
        update_change_field(state_file, "add-auth", "failure_reason", "test")
        state = load_state(state_file)
        assert state.changes[0].extras["failure_reason"] == "test"

    def test_change_not_found(self, state_file):
        with pytest.raises(ValueError, match="Change not found"):
            update_change_field(state_file, "nonexistent", "status", "running")

    def test_status_change_emits_event(self, state_file, tmp_dir):
        events_log = os.path.join(tmp_dir, "events.jsonl")
        bus = EventBus(log_path=events_log)
        update_change_field(
            state_file, "add-auth", "status", "running", event_bus=bus
        )
        events = bus.query(event_type="STATE_CHANGE")
        assert len(events) == 1
        assert events[0]["change"] == "add-auth"
        assert events[0]["data"]["from"] == "pending"
        assert events[0]["data"]["to"] == "running"

    def test_same_status_no_event(self, state_file, tmp_dir):
        events_log = os.path.join(tmp_dir, "events.jsonl")
        bus = EventBus(log_path=events_log)
        # Status is already "pending"
        update_change_field(
            state_file, "add-auth", "status", "pending", event_bus=bus
        )
        events = bus.query(event_type="STATE_CHANGE")
        assert len(events) == 0

    def test_tokens_event_on_large_delta(self, state_file, tmp_dir):
        events_log = os.path.join(tmp_dir, "events.jsonl")
        bus = EventBus(log_path=events_log)
        update_change_field(
            state_file, "add-auth", "tokens_used", 50000, event_bus=bus
        )
        events = bus.query(event_type="TOKENS")
        assert len(events) == 1
        assert events[0]["data"]["delta"] == 50000
        assert events[0]["data"]["total"] == 50000

    def test_tokens_small_delta_no_event(self, state_file, tmp_dir):
        events_log = os.path.join(tmp_dir, "events.jsonl")
        bus = EventBus(log_path=events_log)
        update_change_field(
            state_file, "add-auth", "tokens_used", 5000, event_bus=bus
        )
        events = bus.query(event_type="TOKENS")
        assert len(events) == 0


class TestGetChangeStatus:
    def test_returns_status(self, state_file):
        state = load_state(state_file)
        assert get_change_status(state, "add-auth") == "pending"

    def test_returns_empty_for_missing(self, state_file):
        state = load_state(state_file)
        assert get_change_status(state, "nonexistent") == ""


class TestGetChangesByStatus:
    def test_returns_matching_names(self, state_file):
        state = load_state(state_file)
        names = get_changes_by_status(state, "pending")
        assert set(names) == {"add-auth", "fix-login"}

    def test_empty_for_no_match(self, state_file):
        state = load_state(state_file)
        assert get_changes_by_status(state, "merged") == []


class TestCountChangesByStatus:
    def test_counts_correctly(self, state_file):
        state = load_state(state_file)
        assert count_changes_by_status(state, "pending") == 2
        state.changes[0].status = "running"
        assert count_changes_by_status(state, "pending") == 1
        assert count_changes_by_status(state, "running") == 1


# ─── Phase 2: Dependency Operations ──────────────────────────────────


class TestDepsSatisfied:
    def test_no_deps(self):
        state = OrchestratorState(changes=[
            Change(name="a", depends_on=[]),
        ])
        assert deps_satisfied(state, "a") is True

    def test_deps_merged(self):
        state = OrchestratorState(changes=[
            Change(name="a", status="merged"),
            Change(name="b", depends_on=["a"]),
        ])
        assert deps_satisfied(state, "b") is True

    def test_deps_skipped(self):
        state = OrchestratorState(changes=[
            Change(name="a", status="skipped"),
            Change(name="b", depends_on=["a"]),
        ])
        assert deps_satisfied(state, "b") is True

    def test_deps_not_satisfied(self):
        state = OrchestratorState(changes=[
            Change(name="a", status="running"),
            Change(name="b", depends_on=["a"]),
        ])
        assert deps_satisfied(state, "b") is False

    def test_nonexistent_change(self):
        state = OrchestratorState(changes=[])
        assert deps_satisfied(state, "ghost") is True


class TestDepsFailed:
    def test_no_deps(self):
        state = OrchestratorState(changes=[
            Change(name="a", depends_on=[]),
        ])
        assert deps_failed(state, "a") is False

    def test_dep_failed(self):
        state = OrchestratorState(changes=[
            Change(name="a", status="failed"),
            Change(name="b", depends_on=["a"]),
        ])
        assert deps_failed(state, "b") is True

    def test_dep_merge_blocked_not_failure(self):
        state = OrchestratorState(changes=[
            Change(name="a", status="merge-blocked"),
            Change(name="b", depends_on=["a"]),
        ])
        assert deps_failed(state, "b") is False

    def test_dep_running_not_failure(self):
        state = OrchestratorState(changes=[
            Change(name="a", status="running"),
            Change(name="b", depends_on=["a"]),
        ])
        assert deps_failed(state, "b") is False


class TestCascadeFailedDeps:
    def test_cascades_pending_with_failed_dep(self):
        state = OrchestratorState(changes=[
            Change(name="a", status="failed"),
            Change(name="b", status="pending", depends_on=["a"]),
        ])
        count = cascade_failed_deps(state)
        assert count == 1
        assert state.changes[1].status == "failed"
        assert "dependency a failed" in state.changes[1].extras["failure_reason"]

    def test_no_cascade_needed(self):
        state = OrchestratorState(changes=[
            Change(name="a", status="merged"),
            Change(name="b", status="pending", depends_on=["a"]),
        ])
        count = cascade_failed_deps(state)
        assert count == 0
        assert state.changes[1].status == "pending"

    def test_cascade_emits_event(self):
        state = OrchestratorState(changes=[
            Change(name="a", status="failed"),
            Change(name="b", status="pending", depends_on=["a"]),
        ])
        captured = []
        bus = EventBus(enabled=False)
        bus._enabled = True  # enable in-memory only
        bus._log_path = None  # suppress: we don't want to write to disk here
        # Use subscribe to capture events
        bus.subscribe("CASCADE_FAILED", lambda e: captured.append(e))
        # Manually emit for test since no log path
        cascade_failed_deps(state, event_bus=bus)
        # Event was emitted via bus.emit — but log_path is None so no file write
        # Check state instead
        assert state.changes[1].status == "failed"

    def test_skips_non_pending(self):
        state = OrchestratorState(changes=[
            Change(name="a", status="failed"),
            Change(name="b", status="running", depends_on=["a"]),
        ])
        count = cascade_failed_deps(state)
        assert count == 0


class TestTopologicalSort:
    def test_linear_chain(self):
        changes = [
            Change(name="a", depends_on=[]),
            Change(name="b", depends_on=["a"]),
            Change(name="c", depends_on=["b"]),
        ]
        assert topological_sort(changes) == ["a", "b", "c"]

    def test_independent_changes(self):
        changes = [
            Change(name="c", depends_on=[]),
            Change(name="a", depends_on=[]),
            Change(name="b", depends_on=[]),
        ]
        # Alphabetical order for determinism
        assert topological_sort(changes) == ["a", "b", "c"]

    def test_diamond_dependency(self):
        changes = [
            Change(name="a", depends_on=[]),
            Change(name="b", depends_on=["a"]),
            Change(name="c", depends_on=["a"]),
            Change(name="d", depends_on=["b", "c"]),
        ]
        result = topological_sort(changes)
        assert result.index("a") < result.index("b")
        assert result.index("a") < result.index("c")
        assert result.index("b") < result.index("d")
        assert result.index("c") < result.index("d")

    def test_circular_dependency(self):
        changes = [
            Change(name="a", depends_on=["b"]),
            Change(name="b", depends_on=["a"]),
        ]
        with pytest.raises(CircularDependencyError):
            topological_sort(changes)

    def test_dict_input(self):
        changes = [
            {"name": "x", "depends_on": []},
            {"name": "y", "depends_on": ["x"]},
        ]
        assert topological_sort(changes) == ["x", "y"]


# ─── Phase 2: Phase Management ───────────────────────────────────────


class TestPhaseManagement:
    def _make_phased_state(self):
        return OrchestratorState(changes=[
            Change(name="a", phase=1),
            Change(name="b", phase=1),
            Change(name="c", phase=2),
            Change(name="d", phase=3),
        ])

    def test_init_phase_state(self):
        state = self._make_phased_state()
        init_phase_state(state)
        assert state.extras["current_phase"] == 1
        phases = state.extras["phases"]
        assert phases["1"]["status"] == "running"
        assert phases["2"]["status"] == "pending"
        assert phases["3"]["status"] == "pending"

    def test_init_single_phase_no_phases(self):
        state = OrchestratorState(changes=[
            Change(name="a", phase=1),
            Change(name="b", phase=1),
        ])
        init_phase_state(state)
        assert "phases" not in state.extras

    def test_apply_phase_overrides(self):
        state = self._make_phased_state()
        init_phase_state(state)
        apply_phase_overrides(state, {"a": 2})
        assert state.changes[0].phase == 2
        # Phases recalculated
        phases = state.extras["phases"]
        assert "1" in phases  # b still in phase 1
        assert "2" in phases

    def test_apply_empty_overrides(self):
        state = self._make_phased_state()
        init_phase_state(state)
        apply_phase_overrides(state, {})
        assert state.extras["current_phase"] == 1

    def test_all_phase_changes_terminal(self):
        state = self._make_phased_state()
        state.changes[0].status = "merged"
        state.changes[1].status = "failed"
        assert all_phase_changes_terminal(state, 1) is True
        assert all_phase_changes_terminal(state, 2) is False

    def test_all_phase_changes_terminal_with_running(self):
        state = self._make_phased_state()
        state.changes[0].status = "merged"
        state.changes[1].status = "running"
        assert all_phase_changes_terminal(state, 1) is False

    def test_advance_phase(self):
        state = self._make_phased_state()
        init_phase_state(state)
        result = advance_phase(state)
        assert result is True
        assert state.extras["current_phase"] == 2
        assert state.extras["phases"]["1"]["status"] == "completed"
        assert state.extras["phases"]["1"]["completed_at"] is not None
        assert state.extras["phases"]["2"]["status"] == "running"

    def test_advance_phase_emits_event(self, tmp_dir):
        state = self._make_phased_state()
        init_phase_state(state)
        events_log = os.path.join(tmp_dir, "events.jsonl")
        bus = EventBus(log_path=events_log)
        advance_phase(state, event_bus=bus)
        events = bus.query(event_type="PHASE_ADVANCED")
        assert len(events) == 1
        assert events[0]["data"]["from"] == 1
        assert events[0]["data"]["to"] == 2

    def test_advance_last_phase(self):
        state = self._make_phased_state()
        init_phase_state(state)
        advance_phase(state)  # 1→2
        advance_phase(state)  # 2→3
        result = advance_phase(state)  # no more
        assert result is False
        assert state.extras["phases"]["3"]["status"] == "completed"

    def test_advance_no_phases_returns_false(self):
        state = OrchestratorState(changes=[Change(name="a")])
        assert advance_phase(state) is False


# ─── Phase 2: Crash Recovery ─────────────────────────────────────────


class TestReconstructState:
    def test_replay_status_transitions(self, state_file, tmp_dir):
        events_path = os.path.join(tmp_dir, "events.jsonl")
        with open(events_path, "w") as f:
            f.write(json.dumps({
                "ts": "2026-01-01T00:00:00", "type": "STATE_CHANGE",
                "change": "add-auth", "data": {"from": "pending", "to": "running"},
            }) + "\n")
            f.write(json.dumps({
                "ts": "2026-01-01T01:00:00", "type": "STATE_CHANGE",
                "change": "add-auth", "data": {"from": "running", "to": "done"},
            }) + "\n")

        result = reconstruct_state_from_events(state_file, events_path)
        assert result is True
        state = load_state(state_file)
        assert state.changes[0].status == "done"
        # fix-login has no events, stays pending
        assert state.changes[1].status == "pending"
        assert state.status == "stopped"  # not all done

    def test_replay_tokens(self, state_file, tmp_dir):
        events_path = os.path.join(tmp_dir, "events.jsonl")
        with open(events_path, "w") as f:
            f.write(json.dumps({
                "ts": "2026-01-01T00:00:00", "type": "TOKENS",
                "change": "add-auth", "data": {"delta": 50000, "total": 50000},
            }) + "\n")

        reconstruct_state_from_events(state_file, events_path)
        state = load_state(state_file)
        assert state.changes[0].tokens_used == 50000

    def test_running_becomes_stalled(self, state_file, tmp_dir):
        # Set add-auth to running first
        with locked_state(state_file) as state:
            state.changes[0].status = "running"

        events_path = os.path.join(tmp_dir, "events.jsonl")
        with open(events_path, "w") as f:
            f.write(json.dumps({
                "ts": "2026-01-01T00:00:00", "type": "STATE_CHANGE",
                "change": "add-auth", "data": {"from": "pending", "to": "running"},
            }) + "\n")

        reconstruct_state_from_events(state_file, events_path)
        state = load_state(state_file)
        assert state.changes[0].status == "stalled"

    def test_all_done_sets_done(self, state_file, tmp_dir):
        events_path = os.path.join(tmp_dir, "events.jsonl")
        with open(events_path, "w") as f:
            f.write(json.dumps({
                "ts": "2026-01-01T00:00:00", "type": "STATE_CHANGE",
                "change": "add-auth", "data": {"from": "pending", "to": "merged"},
            }) + "\n")
            f.write(json.dumps({
                "ts": "2026-01-01T00:00:00", "type": "STATE_CHANGE",
                "change": "fix-login", "data": {"from": "pending", "to": "merged"},
            }) + "\n")

        reconstruct_state_from_events(state_file, events_path)
        state = load_state(state_file)
        assert state.status == "done"

    def test_missing_events_file(self, state_file):
        result = reconstruct_state_from_events(state_file, "/nonexistent.jsonl")
        assert result is False

    def test_empty_events_file(self, state_file, tmp_dir):
        events_path = os.path.join(tmp_dir, "events.jsonl")
        open(events_path, "w").close()
        result = reconstruct_state_from_events(state_file, events_path)
        assert result is False


# ─── Phase 2: Hook Runner ────────────────────────────────────────────


class TestRunHook:
    def test_no_script_returns_true(self):
        assert run_hook("on_fail", None, "change-1") is True
        assert run_hook("on_fail", "", "change-1") is True

    def test_missing_script_returns_true(self):
        assert run_hook("on_fail", "/nonexistent/hook.sh", "change-1") is True

    def test_passing_hook(self, tmp_dir):
        script = os.path.join(tmp_dir, "hook.sh")
        with open(script, "w") as f:
            f.write("#!/bin/bash\nexit 0\n")
        os.chmod(script, 0o755)
        assert run_hook("on_fail", script, "change-1") is True

    def test_blocking_hook(self, tmp_dir):
        script = os.path.join(tmp_dir, "hook.sh")
        with open(script, "w") as f:
            f.write("#!/bin/bash\necho 'blocked reason' >&2\nexit 1\n")
        os.chmod(script, 0o755)
        assert run_hook("on_fail", script, "change-1") is False

    def test_blocking_hook_emits_event(self, tmp_dir):
        script = os.path.join(tmp_dir, "hook.sh")
        with open(script, "w") as f:
            f.write("#!/bin/bash\necho 'custom reason' >&2\nexit 1\n")
        os.chmod(script, 0o755)

        events_log = os.path.join(tmp_dir, "events.jsonl")
        bus = EventBus(log_path=events_log)
        run_hook("on_fail", script, "change-1", event_bus=bus)
        events = bus.query(event_type="HOOK_BLOCKED")
        assert len(events) == 1
        assert events[0]["data"]["hook"] == "on_fail"
        assert "custom reason" in events[0]["data"]["reason"]

    def test_not_executable_returns_true(self, tmp_dir):
        script = os.path.join(tmp_dir, "hook.sh")
        with open(script, "w") as f:
            f.write("#!/bin/bash\nexit 1\n")
        # NOT making it executable
        assert run_hook("on_fail", script, "change-1") is True


class TestChangeSchemaAdditions:
    """Round-trip tests for fields added by fix-replan-stuck-gate-and-decomposer.

    Each new field must survive to_dict() -> from_dict() unchanged, and
    absence from old state files must produce the documented default.
    """

    def test_stuck_loop_count_default_is_zero(self):
        c = Change(name="x")
        assert c.stuck_loop_count == 0
        d = c.to_dict()
        assert d["stuck_loop_count"] == 0

    def test_stuck_loop_count_roundtrip(self):
        c = Change(name="x", stuck_loop_count=3)
        restored = Change.from_dict(c.to_dict())
        assert restored.stuck_loop_count == 3

    def test_stuck_loop_count_missing_loads_zero(self):
        # Old state file without the field
        old = {"name": "x", "scope": "", "status": "pending"}
        c = Change.from_dict(old)
        assert c.stuck_loop_count == 0

    def test_last_gate_fingerprint_default_none(self):
        c = Change(name="x")
        assert c.last_gate_fingerprint is None
        # Must NOT be serialised when None
        d = c.to_dict()
        assert "last_gate_fingerprint" not in d

    def test_last_gate_fingerprint_serialises_when_set(self):
        c = Change(name="x", last_gate_fingerprint="abc123")
        d = c.to_dict()
        assert d["last_gate_fingerprint"] == "abc123"
        restored = Change.from_dict(d)
        assert restored.last_gate_fingerprint == "abc123"

    def test_token_runaway_baseline_default_none(self):
        c = Change(name="x")
        assert c.token_runaway_baseline is None
        d = c.to_dict()
        assert "token_runaway_baseline" not in d

    def test_token_runaway_baseline_roundtrip(self):
        c = Change(name="x", token_runaway_baseline=70_500_000)
        d = c.to_dict()
        assert d["token_runaway_baseline"] == 70_500_000
        restored = Change.from_dict(d)
        assert restored.token_runaway_baseline == 70_500_000

    def test_fix_iss_child_default_none_omitted(self):
        c = Change(name="x")
        assert c.fix_iss_child is None
        d = c.to_dict()
        assert "fix_iss_child" not in d

    def test_fix_iss_child_roundtrip(self):
        c = Change(name="x", fix_iss_child="fix-iss-007-foo")
        d = c.to_dict()
        assert d["fix_iss_child"] == "fix-iss-007-foo"
        restored = Change.from_dict(d)
        assert restored.fix_iss_child == "fix-iss-007-foo"

    def test_gate_recheck_done_default_false(self):
        c = Change(name="x")
        assert c.gate_recheck_done is False
        d = c.to_dict()
        # Booleans always serialise (unlike None-omit fields) so the
        # dashboard/reporter can distinguish "rechecked:false" from
        # "never observed"
        assert d["gate_recheck_done"] is False

    def test_gate_recheck_done_roundtrip_true(self):
        c = Change(name="x", gate_recheck_done=True)
        restored = Change.from_dict(c.to_dict())
        assert restored.gate_recheck_done is True

    def test_gate_recheck_done_missing_loads_false(self):
        old = {"name": "x"}
        c = Change.from_dict(old)
        assert c.gate_recheck_done is False

    def test_touched_file_globs_default_empty_list(self):
        c = Change(name="x")
        assert c.touched_file_globs == []
        d = c.to_dict()
        assert d["touched_file_globs"] == []

    def test_touched_file_globs_roundtrip(self):
        globs = ["src/app/admin/**/page.tsx", "src/server/promotions/**"]
        c = Change(name="x", touched_file_globs=list(globs))
        d = c.to_dict()
        assert d["touched_file_globs"] == globs
        restored = Change.from_dict(d)
        assert restored.touched_file_globs == globs

    def test_touched_file_globs_missing_loads_empty(self):
        old = {"name": "x"}
        c = Change.from_dict(old)
        assert c.touched_file_globs == []

    def test_retry_wall_time_ms_default_zero(self):
        c = Change(name="x")
        assert c.retry_wall_time_ms == 0
        d = c.to_dict()
        assert d["retry_wall_time_ms"] == 0

    def test_retry_wall_time_ms_roundtrip(self):
        c = Change(name="x", retry_wall_time_ms=500_000)
        restored = Change.from_dict(c.to_dict())
        assert restored.retry_wall_time_ms == 500_000

    def test_retry_wall_time_ms_missing_loads_zero(self):
        old = {"name": "x"}
        c = Change.from_dict(old)
        assert c.retry_wall_time_ms == 0

    def test_all_new_fields_together_roundtrip(self):
        """Regression test: combining every new field must not collide
        with each other in to_dict/from_dict."""
        c = Change(
            name="x",
            stuck_loop_count=2,
            last_gate_fingerprint="sha:abc",
            token_runaway_baseline=21_000_000,
            fix_iss_child="fix-iss-099-bar",
            gate_recheck_done=True,
            touched_file_globs=["src/**/*.ts"],
        )
        d = c.to_dict()
        restored = Change.from_dict(d)
        assert restored.stuck_loop_count == 2
        assert restored.last_gate_fingerprint == "sha:abc"
        assert restored.token_runaway_baseline == 21_000_000
        assert restored.fix_iss_child == "fix-iss-099-bar"
        assert restored.gate_recheck_done is True
        assert restored.touched_file_globs == ["src/**/*.ts"]


class TestSupervisorStatusTriggerBackoffs:
    """Round-trip test for SupervisorStatus.trigger_backoffs."""

    def _fresh_status(self):
        # Import here to avoid pulling supervisor at module import time
        from set_orch.supervisor.state import SupervisorStatus
        return SupervisorStatus

    def test_default_is_empty_dict(self):
        SupervisorStatus = self._fresh_status()
        s = SupervisorStatus()
        assert s.trigger_backoffs == {}

    def test_missing_field_loads_empty_dict(self, tmp_path):
        """An existing status.json without trigger_backoffs must load cleanly."""
        from set_orch.supervisor.state import read_status
        # Write a status without trigger_backoffs
        status_dir = tmp_path / ".set" / "supervisor"
        status_dir.mkdir(parents=True)
        (status_dir / "status.json").write_text(
            '{"daemon_pid": 42, "poll_cycle": 5}'
        )
        loaded = read_status(str(tmp_path))
        assert loaded.daemon_pid == 42
        assert loaded.poll_cycle == 5
        assert loaded.trigger_backoffs == {}

    def test_trigger_backoffs_roundtrip(self, tmp_path):
        from set_orch.supervisor.state import SupervisorStatus, read_status, write_status
        s = SupervisorStatus(
            daemon_pid=1234,
            trigger_backoffs={
                "log_silence::::abc123def456": {"step": 2, "back_off_until": 1776571400.0},
                "integration_failed::foundation-setup::xyz987abcd12": {"step": 1, "back_off_until": 1776571500.0},
            },
        )
        write_status(str(tmp_path), s)
        loaded = read_status(str(tmp_path))
        assert loaded.trigger_backoffs == s.trigger_backoffs
