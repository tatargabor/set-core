"""Tests for wt_orch.loop — API error classification, backoff, completion, token budget."""

import os
import sys
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lib"))

from wt_orch.loop import (
    ApiErrorResult,
    BackoffState,
    classify_api_error,
    calculate_backoff,
    check_token_budget,
    compute_output_hash,
    detect_idle,
    detect_stall,
    detect_ff_to_apply_transition,
    detect_completion,
    API_BACKOFF_BASE,
    API_BACKOFF_MAX,
    API_BACKOFF_MAX_ATTEMPTS,
)


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ─── classify_api_error ───────────────────────────────────────


class TestClassifyApiError:
    def test_success_exit_not_api_error(self, tmp_dir):
        log = os.path.join(tmp_dir, "test.log")
        with open(log, "w") as f:
            f.write("Some output\n")
        result = classify_api_error(log, 0)
        assert result.is_api_error is False

    def test_rate_limit_429(self, tmp_dir):
        log = os.path.join(tmp_dir, "test.log")
        with open(log, "w") as f:
            f.write("Error: 429 Too Many Requests\n")
        result = classify_api_error(log, 1)
        assert result.is_api_error is True
        assert result.error_type == "rate_limit"

    def test_rate_limit_word(self, tmp_dir):
        log = os.path.join(tmp_dir, "test.log")
        with open(log, "w") as f:
            f.write("API rate limit exceeded\n")
        result = classify_api_error(log, 1)
        assert result.is_api_error is True

    def test_server_500(self, tmp_dir):
        log = os.path.join(tmp_dir, "test.log")
        with open(log, "w") as f:
            f.write("HTTP 500 Internal Server Error\n")
        result = classify_api_error(log, 1)
        assert result.is_api_error is True
        assert result.error_type == "server"

    def test_server_502(self, tmp_dir):
        log = os.path.join(tmp_dir, "test.log")
        with open(log, "w") as f:
            f.write("Bad Gateway 502\n")
        result = classify_api_error(log, 1)
        assert result.is_api_error is True

    def test_connection_reset(self, tmp_dir):
        log = os.path.join(tmp_dir, "test.log")
        with open(log, "w") as f:
            f.write("Error: ECONNRESET\n")
        result = classify_api_error(log, 1)
        assert result.is_api_error is True
        assert result.error_type == "connection"

    def test_connection_refused(self, tmp_dir):
        log = os.path.join(tmp_dir, "test.log")
        with open(log, "w") as f:
            f.write("connect ECONNREFUSED 127.0.0.1:443\n")
        result = classify_api_error(log, 1)
        assert result.is_api_error is True

    def test_generic_error_not_api(self, tmp_dir):
        log = os.path.join(tmp_dir, "test.log")
        with open(log, "w") as f:
            f.write("TypeError: cannot read property\n")
        result = classify_api_error(log, 1)
        assert result.is_api_error is False

    def test_no_file(self):
        result = classify_api_error("/nonexistent", 1)
        assert result.is_api_error is False

    def test_overloaded(self, tmp_dir):
        log = os.path.join(tmp_dir, "test.log")
        with open(log, "w") as f:
            f.write("API overloaded, please retry\n")
        result = classify_api_error(log, 1)
        assert result.is_api_error is True


# ─── BackoffState ─────────────────────────────────────────────


class TestBackoffState:
    def test_initial_state(self):
        bs = BackoffState()
        assert bs.attempt_count == 0
        assert bs.current_delay == API_BACKOFF_BASE
        assert bs.exhausted is False

    def test_next_delay_doubles(self):
        bs = BackoffState()
        d1 = bs.next_delay()
        assert d1 == API_BACKOFF_BASE
        d2 = bs.next_delay()
        assert d2 == API_BACKOFF_BASE * 2

    def test_max_delay_cap(self):
        bs = BackoffState()
        for _ in range(20):
            delay = bs.next_delay()
        assert delay <= API_BACKOFF_MAX

    def test_reset(self):
        bs = BackoffState()
        bs.next_delay()
        bs.next_delay()
        bs.reset()
        assert bs.attempt_count == 0
        assert bs.current_delay == API_BACKOFF_BASE

    def test_exhausted(self):
        bs = BackoffState()
        for _ in range(API_BACKOFF_MAX_ATTEMPTS):
            bs.next_delay()
        assert bs.exhausted is True


# ─── calculate_backoff ────────────────────────────────────────


class TestCalculateBackoff:
    def test_first_attempt(self):
        assert calculate_backoff(0) == API_BACKOFF_BASE

    def test_second_attempt(self):
        assert calculate_backoff(1) == API_BACKOFF_BASE * 2

    def test_max_cap(self):
        assert calculate_backoff(100) == API_BACKOFF_MAX

    def test_custom_base(self):
        assert calculate_backoff(0, base=10) == 10
        assert calculate_backoff(1, base=10) == 20


# ─── check_token_budget ──────────────────────────────────────


class TestCheckTokenBudget:
    def test_no_budget(self):
        assert check_token_budget(99999, 0) == "ok"

    def test_under_budget(self):
        assert check_token_budget(5000, 10000) == "ok"

    def test_warn_threshold(self):
        assert check_token_budget(8000, 10000) == "warn"

    def test_stop_threshold(self):
        assert check_token_budget(10000, 10000) == "stop"

    def test_over_budget(self):
        assert check_token_budget(15000, 10000) == "stop"

    def test_at_79_percent_ok(self):
        assert check_token_budget(79, 100) == "ok"

    def test_at_80_percent_warn(self):
        assert check_token_budget(80, 100) == "warn"


# ─── detect_idle ──────────────────────────────────────────────


class TestDetectIdle:
    def test_different_hash_resets(self):
        count, reached = detect_idle("aaa", "bbb", 2, 3)
        assert count == 0
        assert reached is False

    def test_same_hash_increments(self):
        count, reached = detect_idle("aaa", "aaa", 1, 3)
        assert count == 2
        assert reached is False

    def test_limit_reached(self):
        count, reached = detect_idle("aaa", "aaa", 2, 3)
        assert count == 3
        assert reached is True

    def test_no_previous_hash(self):
        count, reached = detect_idle("aaa", None, 0, 3)
        assert count == 0


# ─── detect_stall ─────────────────────────────────────────────


class TestDetectStall:
    def test_commits_reset(self):
        count, stalled = detect_stall(["abc"], 2, 3)
        assert count == 0
        assert stalled is False

    def test_no_commits_increment(self):
        count, stalled = detect_stall([], 1, 3)
        assert count == 2
        assert stalled is False

    def test_stall_reached(self):
        count, stalled = detect_stall([], 2, 3)
        assert count == 3
        assert stalled is True


# ─── compute_output_hash ──────────────────────────────────────


class TestComputeOutputHash:
    def test_consistent(self):
        assert compute_output_hash("hello") == compute_output_hash("hello")

    def test_different_inputs(self):
        assert compute_output_hash("hello") != compute_output_hash("world")

    def test_empty(self):
        h = compute_output_hash("")
        assert isinstance(h, str)
        assert len(h) == 12


# ─── detect_ff_to_apply_transition ────────────────────────────


class TestFFTransition:
    def test_ff_to_apply(self):
        assert detect_ff_to_apply_transition("ff:ch", "apply:ch") is True

    def test_ff_to_done(self):
        assert detect_ff_to_apply_transition("ff:ch", "done") is False

    def test_apply_to_done(self):
        assert detect_ff_to_apply_transition("apply:ch", "done") is False

    def test_ff_to_ff(self):
        assert detect_ff_to_apply_transition("ff:ch", "ff:ch") is False
