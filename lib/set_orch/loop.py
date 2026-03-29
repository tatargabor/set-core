from __future__ import annotations

"""Loop engine: API error classification, backoff, iteration lifecycle, completion.

1:1 migration of lib/loop/engine.sh — the core iteration loop.
Note: The actual PTY/terminal management stays in bin/set-loop (bash).
This module provides the logic functions called from there.
"""

import hashlib
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional


# ─── Constants ────────────────────────────────────────────────

API_BACKOFF_BASE = 30
API_BACKOFF_MAX = 240
API_BACKOFF_MAX_ATTEMPTS = 10

TOKEN_BUDGET_WARN_PCT = 80
TOKEN_BUDGET_STOP_PCT = 100


# ─── Dataclasses ──────────────────────────────────────────────


@dataclass
class ApiErrorResult:
    """Result of API error classification."""

    is_api_error: bool = False
    error_type: str = ""  # "rate_limit", "server", "connection"
    detail: str = ""


@dataclass
class BackoffState:
    """Tracks exponential backoff state across iterations."""

    attempt_count: int = 0
    current_delay: int = API_BACKOFF_BASE
    max_attempts: int = API_BACKOFF_MAX_ATTEMPTS

    def next_delay(self) -> int:
        """Calculate and advance to next backoff delay."""
        self.attempt_count += 1
        delay = self.current_delay
        self.current_delay = min(self.current_delay * 2, API_BACKOFF_MAX)
        return delay

    def reset(self) -> None:
        self.attempt_count = 0
        self.current_delay = API_BACKOFF_BASE

    @property
    def exhausted(self) -> bool:
        return self.attempt_count >= self.max_attempts


# ─── API Error Classification ─────────────────────────────────


def classify_api_error(log_file: str, exit_code: int) -> ApiErrorResult:
    """Scan log for 429, rate-limit, 5xx patterns.

    Returns ApiErrorResult with is_api_error=True if API error detected.
    """
    if exit_code == 0:
        return ApiErrorResult()
    if not log_file or not os.path.isfile(log_file):
        return ApiErrorResult()

    try:
        with open(log_file, "r", errors="replace") as f:
            # Read last ~50 lines
            lines = f.readlines()
            tail = "".join(lines[-50:])
    except OSError:
        return ApiErrorResult()

    tail_lower = tail.lower()

    # Rate limit errors
    if re.search(r"429|rate.?limit|overloaded|too many requests", tail_lower):
        return ApiErrorResult(
            is_api_error=True,
            error_type="rate_limit",
            detail="Rate limit or overloaded",
        )

    # Server errors
    if re.search(
        r"50[0-3]|internal server error|bad gateway|service unavailable", tail_lower
    ):
        return ApiErrorResult(
            is_api_error=True,
            error_type="server",
            detail="Server error (5xx)",
        )

    # Connection errors
    if re.search(
        r"econnreset|connection reset|etimedout|socket hang up|econnrefused",
        tail_lower,
    ):
        return ApiErrorResult(
            is_api_error=True,
            error_type="connection",
            detail="Connection error",
        )

    return ApiErrorResult()


# ─── Backoff Calculator ───────────────────────────────────────


def calculate_backoff(attempt: int, base: int = API_BACKOFF_BASE, max_delay: int = API_BACKOFF_MAX) -> int:
    """Exponential backoff with base=30s, max=240s."""
    delay = base * (2 ** attempt)
    return min(delay, max_delay)


# ─── Completion Detection ─────────────────────────────────────


def detect_completion(
    wt_path: str,
    done_criteria: str,
    target_change: str = "",
) -> bool:
    """Check if the loop should stop (tasks done, archive action, etc.)."""
    from .loop_tasks import is_done

    return is_done(wt_path, done_criteria, target_change)


# ─── Token Budget ─────────────────────────────────────────────


def check_token_budget(total_tokens: int, budget: int) -> str:
    """Check token budget. Returns: "ok", "warn", or "stop"."""
    if budget <= 0:
        return "ok"
    pct = (total_tokens * 100) // budget
    if pct >= TOKEN_BUDGET_STOP_PCT:
        return "stop"
    if pct >= TOKEN_BUDGET_WARN_PCT:
        return "warn"
    return "ok"


# ─── Stall / Idle Detection ──────────────────────────────────


def compute_output_hash(text: str) -> str:
    """Hash the last ~200 chars of output for idle detection."""
    snippet = text.strip()[-200:] if text else ""
    return hashlib.md5(snippet.encode()).hexdigest()[:12]


def detect_idle(
    output_hash: str,
    last_hash: Optional[str],
    idle_count: int,
    max_idle: int,
) -> tuple:
    """Check if agent is repeating the same output.

    Returns (new_idle_count, is_idle_limit_reached).
    """
    if last_hash and output_hash == last_hash:
        idle_count += 1
    else:
        idle_count = 0
    return idle_count, idle_count >= max_idle


def detect_stall(
    new_commits: list,
    stall_count: int,
    stall_threshold: int,
) -> tuple:
    """Check if agent is making progress (commits).

    Returns (new_stall_count, is_stalled).
    """
    if not new_commits:
        stall_count += 1
    else:
        stall_count = 0
    return stall_count, stall_count >= stall_threshold


# ─── FF Recovery Detection ────────────────────────────────────


def detect_ff_to_apply_transition(pre_action: str, post_action: str) -> bool:
    """Detect when an ff: action transitions to apply: (ff completed within iteration)."""
    return pre_action.startswith("ff:") and post_action.startswith("apply:")
