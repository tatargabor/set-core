from __future__ import annotations

"""Loop state management: state file I/O, token tracking, date parsing, activity.

1:1 migration of lib/loop/state.sh.
"""

import json
import logging
import os
import time
import fcntl
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class LoopState:
    """In-memory representation of loop-state.json."""

    worktree_name: str = ""
    task: str = ""
    done_criteria: str = "tasks"
    max_iterations: int = 20
    current_iteration: int = 0
    status: str = "starting"
    terminal_pid: Optional[int] = None
    started_at: str = ""
    iterations: list = field(default_factory=list)
    capacity_limit_pct: int = 80
    stall_threshold: int = 2
    iteration_timeout_min: int = 45
    total_tokens: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read: int = 0
    total_cache_create: int = 0
    token_budget: int = 0
    ff_attempts: int = 0
    max_idle_iterations: int = 3
    idle_count: int = 0
    last_output_hash: Optional[str] = None
    session_id: Optional[str] = None
    resume_failures: int = 0
    team_mode: bool = False
    label: Optional[str] = None
    change: Optional[str] = None
    permission_mode: str = "default"
    model: Optional[str] = None
    ff_max_retries: int = 2
    test_command: Optional[str] = None


def get_loop_state_file(wt_path: str) -> str:
    """Get loop state file path for a worktree (per-agent ephemeral in .set/)."""
    return os.path.join(wt_path, ".set", "loop-state.json")


def get_loop_log_dir(wt_path: str) -> str:
    return os.path.join(wt_path, ".set", "logs")


def get_iter_log_file(wt_path: str, iteration: int) -> str:
    log_dir = get_loop_log_dir(wt_path)
    return os.path.join(log_dir, f"ralph-iter-{iteration:03d}.log")


def get_terminal_pid_file(wt_path: str) -> str:
    return os.path.join(wt_path, ".set", "ralph-terminal.pid")


def init_loop_state(
    wt_path: str,
    worktree_name: str,
    task: str,
    max_iter: int,
    done_criteria: str = "tasks",
    capacity_limit: int = 80,
    stall_threshold: int = 2,
    iteration_timeout: int = 45,
    label: str = "",
    change: str = "",
) -> LoopState:
    """Initialize loop state and write to disk."""
    os.makedirs(os.path.join(wt_path, ".set", "logs"), exist_ok=True)

    state = LoopState(
        worktree_name=worktree_name,
        task=task,
        done_criteria=done_criteria,
        max_iterations=max_iter,
        started_at=datetime.now(timezone.utc).isoformat(),
        capacity_limit_pct=capacity_limit,
        stall_threshold=stall_threshold,
        iteration_timeout_min=iteration_timeout,
        label=label or None,
        change=change or None,
    )

    state_file = get_loop_state_file(wt_path)
    _write_state(state_file, _state_to_dict(state))
    logger.info("Loop state initialized: wt=%s, max_iter=%d, done_criteria=%s", worktree_name, max_iter, done_criteria)
    return state


def read_loop_state(wt_path: str) -> Optional[LoopState]:
    """Read loop state from disk. Returns None if not found."""
    state_file = get_loop_state_file(wt_path)
    if not os.path.exists(state_file):
        return None
    try:
        with open(state_file, "r") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                data = json.load(f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        return _dict_to_state(data)
    except (json.JSONDecodeError, OSError):
        return None


def update_loop_state(wt_path: str, field: str, value: Any) -> bool:
    """Update a single field in loop state (atomic with flock)."""
    state_file = get_loop_state_file(wt_path)
    if not os.path.exists(state_file):
        logger.warning("Loop state file not found: %s", state_file)
        return False
    try:
        with open(state_file, "r+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                data = json.load(f)
                old_value = data.get(field)
                data[field] = value
                f.seek(0)
                f.truncate()
                json.dump(data, f, indent=2)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        logger.debug("Loop state update: %s = %r (was: %r)", field, value, old_value)
        return True
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to update loop state field %s: %s", field, e)
        return False


def add_iteration(
    wt_path: str,
    iteration: int,
    started: str,
    ended: str,
    done_check: bool,
    commits: list,
    tokens_used: int = 0,
    timed_out: bool = False,
    tokens_estimated: bool = False,
    no_op: bool = False,
    ff_exhausted: bool = False,
    log_file: str = "",
    resumed: bool = False,
    ff_recovered: bool = False,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_create_tokens: int = 0,
    team_spawned: bool = False,
    teammates_count: int = 0,
    team_tasks_parallel: int = 0,
) -> bool:
    """Append an iteration record to loop state."""
    state_file = get_loop_state_file(wt_path)
    if not os.path.exists(state_file):
        return False
    try:
        with open(state_file, "r+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                data = json.load(f)
                entry = {
                    "n": iteration,
                    "started": started,
                    "ended": ended,
                    "done_check": done_check,
                    "commits": commits,
                    "tokens_used": tokens_used,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cache_read_tokens": cache_read_tokens,
                    "cache_create_tokens": cache_create_tokens,
                    "timed_out": timed_out,
                    "tokens_estimated": tokens_estimated,
                    "no_op": no_op,
                    "ff_exhausted": ff_exhausted,
                    "log_file": log_file,
                    "resumed": resumed,
                    "ff_recovered": ff_recovered,
                    "team_spawned": team_spawned,
                    "teammates_count": teammates_count,
                    "team_tasks_parallel": team_tasks_parallel,
                }
                data.setdefault("iterations", []).append(entry)
                f.seek(0)
                f.truncate()
                json.dump(data, f, indent=2)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        logger.info("Iteration %d recorded: tokens=%d, done=%s, no_op=%s, ff_exhausted=%s",
                     iteration, tokens_used, done_check, no_op, ff_exhausted)
        return True
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to add iteration %d: %s", iteration, e)
        return False


# ─── Token tracking ──────────────────────────────────────────


def add_tokens(cli_output: str) -> dict:
    """Parse Claude CLI output for token counts. Returns dict with token fields.

    Looks for patterns like:
      Total tokens: 12345
      Input tokens: 6789
      Output tokens: 5556
      Cache read tokens: 1000
      Cache creation tokens: 500
    """
    import re

    result = {
        "total_tokens": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_create_tokens": 0,
    }

    patterns = {
        "total_tokens": r"[Tt]otal\s+tokens?:?\s*(\d+)",
        "input_tokens": r"[Ii]nput\s+tokens?:?\s*(\d+)",
        "output_tokens": r"[Oo]utput\s+tokens?:?\s*(\d+)",
        "cache_read_tokens": r"[Cc]ache\s+read\s+tokens?:?\s*(\d+)",
        "cache_create_tokens": r"[Cc]ache\s+creat\w*\s+tokens?:?\s*(\d+)",
    }

    for key, pattern in patterns.items():
        m = re.search(pattern, cli_output)
        if m:
            result[key] = int(m.group(1))

    # If total not found, compute from input + output
    if result["total_tokens"] == 0 and (
        result["input_tokens"] > 0 or result["output_tokens"] > 0
    ):
        result["total_tokens"] = result["input_tokens"] + result["output_tokens"]

    return result


# ─── Date parsing ─────────────────────────────────────────────


def parse_date_to_epoch(date_str: str) -> int:
    """Cross-platform ISO 8601 → epoch seconds.

    Handles formats like:
      2024-01-15T10:30:00+00:00
      2024-01-15T10:30:00Z
      2024-01-15T10:30:00
    """
    if not date_str:
        return 0
    try:
        # Try fromisoformat (Python 3.7+, handles +HH:MM in 3.11+)
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except (ValueError, AttributeError):
        pass
    # Fallback: strip timezone suffix and parse naive
    try:
        import re

        clean = re.sub(r"[+-]\d{2}:?\d{2}$", "", date_str)
        clean = clean.rstrip("Z")
        dt = datetime.strptime(clean, "%Y-%m-%dT%H:%M:%S")
        return int(dt.timestamp())
    except (ValueError, AttributeError):
        return 0


# ─── Activity file ────────────────────────────────────────────


def write_activity(
    wt_path: str,
    skill: str = "",
    skill_args: str = "",
    iteration: int = 0,
    tokens: int = 0,
    pid: int = 0,
    broadcast: str = "",
) -> bool:
    """Write activity.json for monitoring (skill, iteration, tokens, pid)."""
    activity_file = os.path.join(wt_path, ".set", "activity.json")
    os.makedirs(os.path.dirname(activity_file), exist_ok=True)
    data = {
        "skill": skill,
        "skill_args": skill_args,
        "iteration": iteration,
        "tokens": tokens,
        "pid": pid or os.getpid(),
        "broadcast": broadcast,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        tmp = activity_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, activity_file)
        return True
    except OSError:
        return False


# ─── Internal helpers ─────────────────────────────────────────


def _state_to_dict(state: LoopState) -> dict:
    """Convert LoopState to JSON-serializable dict."""
    return asdict(state)


def _dict_to_state(data: dict) -> LoopState:
    """Convert dict to LoopState, ignoring unknown fields."""
    known_fields = {f.name for f in LoopState.__dataclass_fields__.values()}
    filtered = {k: v for k, v in data.items() if k in known_fields}
    return LoopState(**filtered)


def _write_state(state_file: str, data: dict) -> None:
    """Atomic write of state file with flock."""
    tmp = state_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, state_file)
