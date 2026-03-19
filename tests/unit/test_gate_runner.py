"""Tests for wt_orch.gate_runner — GatePipeline execution, retry, skip, batch commit."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from wt_orch.gate_runner import GatePipeline, GateResult
from wt_orch.state import Change, OrchestratorState, load_state, save_state


class FakeGateConfig:
    """Minimal GateConfig stand-in for testing."""

    def __init__(self, gates=None):
        self._gates = gates or {}

    def should_run(self, name):
        mode = self._gates.get(name, "run")
        return mode in ("run", "warn", "soft")

    def is_blocking(self, name):
        mode = self._gates.get(name, "run")
        return mode == "run"


def _make_state(tmp_path, changes=None, **kwargs):
    state_file = str(tmp_path / "state.json")
    state = OrchestratorState(
        status="running",
        changes=changes or [Change(name="c1", status="running")],
        **kwargs,
    )
    save_state(state, state_file)
    return state_file


class TestGatePipelineSkip:
    """Skipped gates produce skip result without calling executor."""

    def test_skipped_gate_not_called(self, tmp_path):
        state_file = _make_state(tmp_path)
        gc = FakeGateConfig(gates={"build": "skip"})
        change = Change(name="c1", status="running")

        pipeline = GatePipeline(gc, state_file, "c1", change, max_retries=2)

        called = []
        pipeline.register("build", lambda: called.append(1) or GateResult("build", "pass"))

        action = pipeline.run()

        assert action == "continue"
        assert called == []  # executor NOT called
        assert len(pipeline.results) == 1
        assert pipeline.results[0].status == "skipped"
        assert pipeline.results[0].gate_name == "build"


class TestGatePipelinePass:
    """All gates passing produces 'continue' action."""

    def test_all_pass(self, tmp_path):
        state_file = _make_state(tmp_path)
        gc = FakeGateConfig()
        change = Change(name="c1", status="running")

        pipeline = GatePipeline(gc, state_file, "c1", change, max_retries=2)
        pipeline.register("build", lambda: GateResult("build", "pass"))
        pipeline.register("test", lambda: GateResult("test", "pass"))

        action = pipeline.run()

        assert action == "continue"
        assert len(pipeline.results) == 2
        assert all(r.status == "pass" for r in pipeline.results)


class TestGatePipelineBlockingFailWithRetry:
    """Blocking failure with retries available returns 'retry'."""

    def test_blocking_fail_retry(self, tmp_path):
        state_file = _make_state(tmp_path)
        gc = FakeGateConfig(gates={"test": "run"})
        change = Change(name="c1", status="running", verify_retry_count=0)

        pipeline = GatePipeline(gc, state_file, "c1", change, max_retries=2)
        pipeline.register("build", lambda: GateResult("build", "pass"))
        pipeline.register("test", lambda: GateResult("test", "fail", retry_context="Fix tests"))

        action = pipeline.run()

        assert action == "retry"
        assert pipeline.stopped is True
        assert pipeline.stop_gate == "test"
        # verify_retry_count should be incremented
        state = load_state(state_file)
        c1 = [c for c in state.changes if c.name == "c1"][0]
        assert c1.verify_retry_count == 1
        assert c1.status == "verify-failed"

    def test_subsequent_gates_not_executed(self, tmp_path):
        state_file = _make_state(tmp_path)
        gc = FakeGateConfig()
        change = Change(name="c1", status="running", verify_retry_count=0)

        review_called = []
        pipeline = GatePipeline(gc, state_file, "c1", change, max_retries=2)
        pipeline.register("test", lambda: GateResult("test", "fail"))
        pipeline.register("review", lambda: review_called.append(1) or GateResult("review", "pass"))

        pipeline.run()

        assert review_called == []  # review NOT called after test fail


class TestGatePipelineBlockingFailExhausted:
    """Blocking failure with retries exhausted returns 'failed'."""

    def test_exhausted_retries(self, tmp_path):
        state_file = _make_state(tmp_path)
        gc = FakeGateConfig()
        change = Change(name="c1", status="running", verify_retry_count=2)

        pipeline = GatePipeline(gc, state_file, "c1", change, max_retries=2)
        pipeline.register("test", lambda: GateResult("test", "fail"))

        action = pipeline.run()

        assert action == "failed"
        state = load_state(state_file)
        c1 = [c for c in state.changes if c.name == "c1"][0]
        assert c1.status == "failed"


class TestGatePipelineWarnFail:
    """Non-blocking failure converts to warn-fail and continues."""

    def test_warn_fail_continues(self, tmp_path):
        state_file = _make_state(tmp_path)
        gc = FakeGateConfig(gates={"test": "warn"})
        change = Change(name="c1", status="running")

        review_called = []
        pipeline = GatePipeline(gc, state_file, "c1", change, max_retries=2)
        pipeline.register("test", lambda: GateResult("test", "fail"))
        pipeline.register("review", lambda: review_called.append(1) or GateResult("review", "pass"))

        action = pipeline.run()

        assert action == "continue"
        assert review_called == [1]  # review WAS called
        assert pipeline.results[0].status == "warn-fail"
        assert pipeline.results[1].status == "pass"


class TestGatePipelineOwnRetryCounter:
    """Gates with own_retry_counter use separate budget."""

    def test_own_counter_incremented(self, tmp_path):
        state_file = _make_state(tmp_path)
        gc = FakeGateConfig()
        change = Change(name="c1", status="running", extras={"build_fix_count": 0})

        pipeline = GatePipeline(gc, state_file, "c1", change, max_retries=2)
        pipeline.register(
            "build",
            lambda: GateResult("build", "fail", retry_context="Fix build"),
            own_retry_counter="build_fix_count",
        )

        action = pipeline.run()

        assert action == "retry"
        state = load_state(state_file)
        c1 = [c for c in state.changes if c.name == "c1"][0]
        assert c1.extras.get("build_fix_count") == 1
        # verify_retry_count should NOT be touched
        assert c1.verify_retry_count == 0


class TestGatePipelineExtraRetries:
    """Gates with extra_retries get additional retry budget."""

    def test_extra_retries_extend_limit(self, tmp_path):
        state_file = _make_state(tmp_path)
        gc = FakeGateConfig()
        # verify_retry_count=2, max_retries=2 → normally exhausted
        change = Change(name="c1", status="running", verify_retry_count=2)

        pipeline = GatePipeline(gc, state_file, "c1", change, max_retries=2)
        pipeline.register(
            "review",
            lambda: GateResult("review", "fail", retry_context="Fix review"),
            extra_retries=1,  # limit becomes 2+1=3
        )

        action = pipeline.run()

        # Should retry because 2 < 3
        assert action == "retry"


class TestGatePipelineCommitResults:
    """commit_results writes all results in single locked_state block."""

    def test_batch_write(self, tmp_path):
        state_file = _make_state(tmp_path)
        gc = FakeGateConfig()
        change = Change(name="c1", status="running")

        pipeline = GatePipeline(gc, state_file, "c1", change, max_retries=2)
        pipeline.register("build", lambda: GateResult("build", "pass"))
        pipeline.register("test", lambda: GateResult("test", "pass", stats={"passed": 5, "failed": 0}))

        pipeline.run()
        summary = pipeline.commit_results()

        # Verify state was updated
        state = load_state(state_file)
        c1 = [c for c in state.changes if c.name == "c1"][0]
        assert c1.build_result == "pass"
        assert c1.test_result == "pass"
        assert c1.test_stats == {"passed": 5, "failed": 0}
        assert summary["build"] == "pass"
        assert summary["test"] == "pass"
        assert summary["total_ms"] >= 0

    def test_partial_results_on_early_exit(self, tmp_path):
        state_file = _make_state(tmp_path)
        gc = FakeGateConfig()
        change = Change(name="c1", status="running", verify_retry_count=0)

        pipeline = GatePipeline(gc, state_file, "c1", change, max_retries=2)
        pipeline.register("build", lambda: GateResult("build", "pass"))
        pipeline.register("test", lambda: GateResult("test", "fail"))

        pipeline.run()
        summary = pipeline.commit_results()

        state = load_state(state_file)
        c1 = [c for c in state.changes if c.name == "c1"][0]
        assert c1.build_result == "pass"
        # test_result written even on failure
        assert c1.test_result == "fail"
        assert "build" in summary
        assert "test" in summary
