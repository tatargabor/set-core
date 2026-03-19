"""Tests for set_orch.loop_state — state round-trip, token parsing, date parsing, activity write."""

import json
import os
import sys
import tempfile
import shutil
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from set_orch.loop_state import (
    LoopState,
    init_loop_state,
    read_loop_state,
    update_loop_state,
    add_iteration,
    add_tokens,
    parse_date_to_epoch,
    write_activity,
    get_loop_state_file,
    get_loop_log_dir,
    get_iter_log_file,
    get_terminal_pid_file,
)


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def wt(tmp_dir):
    """Create a fake worktree with .set/ dir."""
    wt = os.path.join(tmp_dir, "worktree")
    os.makedirs(os.path.join(wt, ".set", "logs"))
    return wt


# ─── Path helpers ─────────────────────────────────────────────


class TestPathHelpers:
    def test_state_file_path(self, wt):
        assert get_loop_state_file(wt).endswith(".set/loop-state.json")

    def test_log_dir_path(self, wt):
        assert get_loop_log_dir(wt).endswith(".set/logs")

    def test_iter_log_file(self, wt):
        path = get_iter_log_file(wt, 5)
        assert path.endswith("ralph-iter-005.log")

    def test_terminal_pid_file(self, wt):
        assert get_terminal_pid_file(wt).endswith("ralph-terminal.pid")


# ─── State round-trip ──────────────────────────────────────────


class TestStateRoundTrip:
    def test_init_and_read(self, wt):
        state = init_loop_state(
            wt, "my-wt", "do stuff", max_iter=10, done_criteria="tasks"
        )
        assert state.worktree_name == "my-wt"
        assert state.max_iterations == 10
        assert state.status == "starting"

        loaded = read_loop_state(wt)
        assert loaded is not None
        assert loaded.worktree_name == "my-wt"
        assert loaded.task == "do stuff"
        assert loaded.max_iterations == 10

    def test_read_nonexistent(self, tmp_dir):
        assert read_loop_state(tmp_dir) is None

    def test_update_field(self, wt):
        init_loop_state(wt, "wt", "task", 5)
        assert update_loop_state(wt, "status", "running")
        loaded = read_loop_state(wt)
        assert loaded.status == "running"

    def test_update_nonexistent(self, tmp_dir):
        assert update_loop_state(tmp_dir, "status", "running") is False

    def test_init_with_label_and_change(self, wt):
        state = init_loop_state(
            wt, "wt", "task", 5, label="my-label", change="my-change"
        )
        assert state.label == "my-label"
        assert state.change == "my-change"

    def test_init_empty_label_is_none(self, wt):
        state = init_loop_state(wt, "wt", "task", 5, label="", change="")
        assert state.label is None
        assert state.change is None

    def test_add_iteration(self, wt):
        init_loop_state(wt, "wt", "task", 5)
        result = add_iteration(
            wt,
            iteration=1,
            started="2024-01-01T00:00:00Z",
            ended="2024-01-01T00:10:00Z",
            done_check=False,
            commits=["abc123"],
            tokens_used=1000,
        )
        assert result is True

        loaded = read_loop_state(wt)
        assert len(loaded.iterations) == 1
        assert loaded.iterations[0]["n"] == 1
        assert loaded.iterations[0]["commits"] == ["abc123"]

    def test_add_multiple_iterations(self, wt):
        init_loop_state(wt, "wt", "task", 5)
        for i in range(3):
            add_iteration(wt, i + 1, "s", "e", False, [])
        loaded = read_loop_state(wt)
        assert len(loaded.iterations) == 3


# ─── Token parsing ────────────────────────────────────────────


class TestAddTokens:
    def test_parse_all_fields(self):
        output = (
            "Total tokens: 12345\n"
            "Input tokens: 6789\n"
            "Output tokens: 5556\n"
            "Cache read tokens: 1000\n"
            "Cache creation tokens: 500\n"
        )
        result = add_tokens(output)
        assert result["total_tokens"] == 12345
        assert result["input_tokens"] == 6789
        assert result["output_tokens"] == 5556
        assert result["cache_read_tokens"] == 1000
        assert result["cache_create_tokens"] == 500

    def test_compute_total_from_parts(self):
        output = "Input tokens: 100\nOutput tokens: 200\n"
        result = add_tokens(output)
        assert result["total_tokens"] == 300

    def test_empty_output(self):
        result = add_tokens("")
        assert result["total_tokens"] == 0

    def test_no_match(self):
        result = add_tokens("some random output\nno token info here")
        assert result["total_tokens"] == 0

    def test_partial_match(self):
        result = add_tokens("Input tokens: 500\n")
        assert result["input_tokens"] == 500
        assert result["total_tokens"] == 500


# ─── Date parsing ─────────────────────────────────────────────


class TestParseDateToEpoch:
    def test_iso_with_tz(self):
        epoch = parse_date_to_epoch("2024-01-15T10:30:00+00:00")
        assert epoch > 0

    def test_iso_with_z(self):
        epoch = parse_date_to_epoch("2024-01-15T10:30:00Z")
        assert epoch > 0

    def test_iso_naive(self):
        epoch = parse_date_to_epoch("2024-01-15T10:30:00")
        assert epoch > 0

    def test_empty_string(self):
        assert parse_date_to_epoch("") == 0

    def test_invalid_string(self):
        assert parse_date_to_epoch("not-a-date") == 0

    def test_consistency(self):
        """Same datetime in different formats should give same epoch."""
        e1 = parse_date_to_epoch("2024-01-15T10:30:00+00:00")
        e2 = parse_date_to_epoch("2024-01-15T10:30:00Z")
        assert e1 == e2


# ─── Activity write ───────────────────────────────────────────


class TestWriteActivity:
    def test_write_and_read(self, wt):
        result = write_activity(
            wt, skill="opsx:apply", skill_args="my-change", iteration=3, tokens=5000
        )
        assert result is True

        activity_file = os.path.join(wt, ".set", "activity.json")
        assert os.path.isfile(activity_file)

        with open(activity_file, "r") as f:
            data = json.load(f)
        assert data["skill"] == "opsx:apply"
        assert data["iteration"] == 3
        assert data["tokens"] == 5000

    def test_write_with_broadcast(self, wt):
        write_activity(wt, broadcast="working on auth")
        activity_file = os.path.join(wt, ".set", "activity.json")
        with open(activity_file, "r") as f:
            data = json.load(f)
        assert data["broadcast"] == "working on auth"

    def test_overwrite(self, wt):
        write_activity(wt, skill="first")
        write_activity(wt, skill="second")
        activity_file = os.path.join(wt, ".set", "activity.json")
        with open(activity_file, "r") as f:
            data = json.load(f)
        assert data["skill"] == "second"


# ─── LoopState dataclass ─────────────────────────────────────


class TestLoopStateDataclass:
    def test_defaults(self):
        s = LoopState()
        assert s.status == "starting"
        assert s.max_iterations == 20
        assert s.iterations == []
        assert s.team_mode is False

    def test_with_values(self):
        s = LoopState(worktree_name="wt", task="build", max_iterations=10)
        assert s.worktree_name == "wt"
        assert s.task == "build"

    def test_test_command_default_none(self):
        s = LoopState()
        assert s.test_command is None

    def test_test_command_roundtrip(self, wt):
        """test_command field survives write→read cycle."""
        from set_orch.loop_state import _state_to_dict, _dict_to_state

        s = LoopState(test_command="pnpm test")
        d = _state_to_dict(s)
        assert d["test_command"] == "pnpm test"

        restored = _dict_to_state(d)
        assert restored.test_command == "pnpm test"

    def test_test_command_none_roundtrip(self, wt):
        """None test_command serializes as null and deserializes back to None."""
        from set_orch.loop_state import _state_to_dict, _dict_to_state

        s = LoopState(test_command=None)
        d = _state_to_dict(s)
        assert d["test_command"] is None

        restored = _dict_to_state(d)
        assert restored.test_command is None
