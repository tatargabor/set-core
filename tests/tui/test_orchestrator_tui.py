"""Tests for orchestrator TUI — state reader, formatting, and approval."""

import json
import os
import tempfile
from pathlib import Path

import pytest

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from gui.tui.orchestrator_tui import (
    StateReader,
    format_tokens,
    format_duration,
    format_change_duration,
    format_gates,
    gate_str,
    GATE_PASS,
    GATE_FAIL,
    GATE_NONE,
)


# ─── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


def make_state(tmp_dir, data):
    """Write orchestration-state.json and return path."""
    path = tmp_dir / "orchestration-state.json"
    with open(path, "w") as f:
        json.dump(data, f)
    return path


def make_log(tmp_dir, lines):
    """Write orchestration log and return path."""
    path = tmp_dir / "orchestration.log"
    with open(path, "w") as f:
        f.writelines(line + "\n" for line in lines)
    return path


MINIMAL_STATE = {
    "status": "running",
    "plan_version": 3,
    "changes": [
        {"name": "change-a", "status": "done", "tokens_used": 50000, "depends_on": [],
         "test_result": "pass", "build_result": "pass", "review_result": "pass"},
        {"name": "change-b", "status": "running", "tokens_used": 10000, "depends_on": ["change-a"],
         "test_result": "pass", "build_result": None, "review_result": None},
        {"name": "change-c", "status": "pending", "tokens_used": 0, "depends_on": [],
         "test_result": None, "build_result": None, "review_result": None},
    ],
    "checkpoints": [],
    "replan_cycle": 0,
    "prev_total_tokens": 0,
    "active_seconds": 1800,
    "started_epoch": 1772282029,
    "time_limit_secs": 18000,
}


# ─── 9.1: StateReader.read_state() ───────────────────────────────────

class TestReadState:
    def test_valid_json(self, tmp_dir):
        path = make_state(tmp_dir, MINIMAL_STATE)
        reader = StateReader(path, tmp_dir / "log")
        state = reader.read_state()
        assert state is not None
        assert state["status"] == "running"
        assert state["plan_version"] == 3
        assert len(state["changes"]) == 3

    def test_malformed_json(self, tmp_dir):
        path = tmp_dir / "orchestration-state.json"
        path.write_text("{broken json!!!")
        reader = StateReader(path, tmp_dir / "log")
        assert reader.read_state() is None

    def test_missing_file(self, tmp_dir):
        reader = StateReader(tmp_dir / "nonexistent.json", tmp_dir / "log")
        assert reader.read_state() is None


# ─── 9.2: StateReader.read_log() offset tracking ─────────────────────

class TestReadLog:
    def test_first_read_gets_last_200(self, tmp_dir):
        lines = [f"[2026-02-28] [INFO] Line {i}" for i in range(300)]
        log_path = make_log(tmp_dir, lines)
        reader = StateReader(tmp_dir / "state.json", log_path)
        result = reader.read_log()
        assert result is not None
        assert len(result) == 200

    def test_incremental_read(self, tmp_dir):
        log_path = tmp_dir / "orchestration.log"
        log_path.write_text("line 1\nline 2\n")
        reader = StateReader(tmp_dir / "state.json", log_path)

        # First read
        first = reader.read_log()
        assert len(first) == 2

        # Append more
        with open(log_path, "a") as f:
            f.write("line 3\nline 4\n")

        # Second read — only new lines
        second = reader.read_log()
        assert len(second) == 2
        assert "line 3" in second[0]
        assert "line 4" in second[1]

    def test_no_log_file(self, tmp_dir):
        reader = StateReader(tmp_dir / "state.json", tmp_dir / "nofile.log")
        assert reader.read_log() is None

    def test_log_rotation(self, tmp_dir):
        log_path = tmp_dir / "orchestration.log"
        log_path.write_text("old line 1\nold line 2\n")
        reader = StateReader(tmp_dir / "state.json", log_path)
        reader.read_log()  # first read, sets offset

        # Simulate log rotation — file is now smaller
        log_path.write_text("new line 1\n")
        result = reader.read_log()
        assert result is not None
        assert any("new line 1" in l for l in result)


# ─── 9.3: Header formatting helpers ──────────────────────────────────

class TestFormatHelpers:
    def test_format_tokens(self):
        assert format_tokens(0) == "-"
        assert format_tokens(None) == "-"
        assert format_tokens(500) == "500"
        assert format_tokens(5000) == "5K"
        assert format_tokens(50000) == "50K"
        assert format_tokens(1500000) == "1.5M"

    def test_format_duration(self):
        assert format_duration(0) == "-"
        assert format_duration(None) == "-"
        assert format_duration(30) == "30s"
        assert format_duration(120) == "2m"
        assert format_duration(3600) == "1h"
        assert format_duration(5400) == "1h30m"
        assert format_duration(18000) == "5h"


# ─── 9.4: Approve action ─────────────────────────────────────────────

class TestApprove:
    def test_approve_writes_atomically(self, tmp_dir):
        state_data = {
            "status": "checkpoint",
            "checkpoints": [
                {"reason": "periodic", "approved": False}
            ],
            "changes": [],
        }
        state_path = make_state(tmp_dir, state_data)

        # Simulate what action_approve does
        with open(state_path) as f:
            data = json.load(f)

        data["checkpoints"][-1]["approved"] = True
        data["checkpoints"][-1]["approved_at"] = "2026-02-28T12:00:00+00:00"

        fd, tmp_path = tempfile.mkstemp(dir=tmp_dir, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.rename(tmp_path, state_path)

        # Verify
        with open(state_path) as f:
            result = json.load(f)
        assert result["checkpoints"][-1]["approved"] is True
        assert "approved_at" in result["checkpoints"][-1]

    def test_approve_not_at_checkpoint(self, tmp_dir):
        state_data = {"status": "running", "checkpoints": [], "changes": []}
        path = make_state(tmp_dir, state_data)
        reader = StateReader(path, tmp_dir / "log")
        state = reader.read_state()
        assert state["status"] != "checkpoint"


# ─── 9.5: Gate formatting ────────────────────────────────────────────

class TestGateFormatting:
    def test_all_pass_with_smoke(self):
        # Merged change with post-merge smoke — shows T/B/R/V + S
        change = {"test_result": "pass", "build_result": "pass",
                  "smoke_result": "pass", "review_result": "pass", "status": "merged"}
        result = format_gates(change)
        assert "T" in result and "B" in result and "R" in result and "V" in result and "S" in result
        assert result.count("✓") == 5

    def test_pre_merge_no_smoke(self):
        # Done (pre-merge) change — no smoke column
        change = {"test_result": "pass", "build_result": "pass",
                  "smoke_result": None, "review_result": "pass", "status": "done"}
        result = format_gates(change)
        assert "T" in result and "B" in result and "R" in result and "V" in result
        assert "S" not in result
        assert result.count("✓") == 4

    def test_build_fail(self):
        change = {"test_result": "pass", "build_result": "fail",
                  "review_result": None, "status": "failed"}
        result = format_gates(change)
        assert "✓" in result  # test passed
        assert "✗" in result  # build failed

    def test_pending_no_gates(self):
        change = {"test_result": None, "build_result": None,
                  "smoke_result": None, "review_result": None, "status": "pending"}
        result = format_gates(change)
        # T/B/R/V all NONE, no S (smoke is None)
        assert result.count("-") == 4
        assert "S" not in result

    def test_verify_pass_when_merged(self):
        change = {"test_result": "pass", "build_result": "pass",
                  "smoke_result": "pass", "review_result": "pass", "status": "merged"}
        result = format_gates(change)
        assert result.count("✓") == 5

    def test_verify_fail(self):
        change = {"test_result": "pass", "build_result": "pass",
                  "smoke_result": None, "review_result": "pass", "status": "verify-failed"}
        result = format_gates(change)
        # T, B, R pass but V fails, no S (not merged yet)
        assert result.count("✓") == 3
        assert "✗" in result  # verify failed
        assert "S" not in result

    def test_gate_str(self):
        assert gate_str("pass") == GATE_PASS
        assert gate_str("fail") == GATE_FAIL
        assert gate_str(None) == GATE_NONE
        assert gate_str("unknown") == GATE_NONE


# ─── 9.6: Token display during replan ───────────────────────────────

class TestTokenReplanPersistence:
    """During replan transition, current cycle tokens are 0.
    The TUI should show prev_total_tokens instead of 0."""

    def test_replan_shows_prev_tokens(self):
        """When current_tokens=0 and prev_total_tokens>0, total should be prev."""
        current_tokens = 0
        prev_tokens = 3500000
        # Logic from _update_header
        if current_tokens == 0 and prev_tokens > 0:
            total_tokens = prev_tokens
        else:
            total_tokens = current_tokens + prev_tokens
        assert total_tokens == 3500000
        assert format_tokens(total_tokens) == "3.5M"

    def test_normal_accumulation(self):
        """Normal case: both current and prev are summed."""
        current_tokens = 500000
        prev_tokens = 3000000
        if current_tokens == 0 and prev_tokens > 0:
            total_tokens = prev_tokens
        else:
            total_tokens = current_tokens + prev_tokens
        assert total_tokens == 3500000

    def test_first_cycle_no_prev(self):
        """First cycle: no prev tokens, current only."""
        current_tokens = 500000
        prev_tokens = 0
        if current_tokens == 0 and prev_tokens > 0:
            total_tokens = prev_tokens
        else:
            total_tokens = current_tokens + prev_tokens
        assert total_tokens == 500000


# ─── Per-change duration ─────────────────────────────────────────────

class TestFormatChangeDuration:
    def test_completed_change(self):
        change = {
            "started_at": "2026-03-09T11:22:20+01:00",
            "completed_at": "2026-03-09T11:43:25+01:00",
        }
        result = format_change_duration(change)
        assert result == "21m"

    def test_no_started_at(self):
        change = {"completed_at": "2026-03-09T11:43:25+01:00"}
        assert format_change_duration(change) == "-"

    def test_empty_change(self):
        assert format_change_duration({}) == "-"

    def test_short_duration(self):
        change = {
            "started_at": "2026-03-09T11:22:20+01:00",
            "completed_at": "2026-03-09T11:22:50+01:00",
        }
        assert format_change_duration(change) == "30s"

    def test_long_duration(self):
        change = {
            "started_at": "2026-03-09T11:00:00+01:00",
            "completed_at": "2026-03-09T12:05:00+01:00",
        }
        assert format_change_duration(change) == "1h05m"


# ─── Smoke fix gate display ─────────────────────────────────────────

class TestSmokeFixGate:
    def test_smoke_pass_no_fix(self):
        change = {"test_result": "pass", "build_result": "pass",
                  "smoke_result": "pass", "review_result": "pass",
                  "status": "merged"}
        result = format_gates(change)
        assert "S" in result
        assert "(fix)" not in result

    def test_smoke_pass_with_smoke_fixed(self):
        change = {"test_result": "pass", "build_result": "pass",
                  "smoke_result": "pass", "review_result": "pass",
                  "status": "merged", "smoke_fixed": True}
        result = format_gates(change)
        assert "(fix)" in result

    def test_smoke_pass_with_smoke_status_fixed(self):
        change = {"test_result": "pass", "build_result": "pass",
                  "smoke_result": "pass", "review_result": "pass",
                  "status": "merged", "smoke_status": "fixed"}
        result = format_gates(change)
        assert "(fix)" in result

    def test_smoke_fail(self):
        change = {"test_result": "pass", "build_result": "pass",
                  "smoke_result": "fail", "review_result": "pass",
                  "status": "merged"}
        result = format_gates(change)
        assert "S" in result
        assert "✗" in result
        assert "(fix)" not in result


# ─── Summary row token calculation ──────────────────────────────────

class TestSummaryRowTokens:
    def test_total_billed_tokens(self):
        changes = [
            {"input_tokens": 100000, "output_tokens": 10000, "cache_read_tokens": 500000},
            {"input_tokens": 200000, "output_tokens": 20000, "cache_read_tokens": 800000},
        ]
        total_billed = sum((c.get("input_tokens") or 0) + (c.get("output_tokens") or 0) for c in changes)
        assert total_billed == 330000
        assert format_tokens(total_billed) == "330K"

    def test_missing_token_fields(self):
        changes = [
            {"input_tokens": 100000},
            {"output_tokens": 20000},
            {},
        ]
        total_billed = sum((c.get("input_tokens") or 0) + (c.get("output_tokens") or 0) for c in changes)
        assert total_billed == 120000
