from __future__ import annotations

"""Orchestration watchdog: per-change health monitoring, timeout, loop detection, escalation.

Migrated from: lib/orchestration/watchdog.sh (424 LOC)
Provides: watchdog_check(), watchdog_init_state(), detect_hash_loop(),
          escalation logic, watchdog_heartbeat(), progress-based trend detection.
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────────
# Migrated from: watchdog.sh L18-25

# Per-state timeout defaults (seconds). Overridden by watchdog_timeout directive.
WATCHDOG_TIMEOUT_RUNNING = 600
WATCHDOG_TIMEOUT_VERIFYING = 300
WATCHDOG_TIMEOUT_DISPATCHED = 120

# Loop detection: consecutive identical action hashes before declaring stuck
WATCHDOG_LOOP_THRESHOLD = 5
WATCHDOG_HASH_RING_SIZE = 5


# Idle detection threshold (seconds) — emit IDLE_START after this gap
IDLE_THRESHOLD_SECONDS = 60

# Module-level idle state tracker
_idle_active = False


def reset_idle_state() -> None:
    """Reset the idle detection state. Call between test runs or on restart."""
    global _idle_active
    _idle_active = False


# ─── Dataclasses ─────────────────────────────────────────────────


@dataclass
class WatchdogResult:
    """Result of a watchdog check for one change."""

    action: str  # ok, restart, redispatch, fail, warn
    reason: str
    escalation_level: int = 0


# ─── Watchdog Check ─────────────────────────────────────────────
# Migrated from: watchdog.sh:watchdog_check()


def watchdog_check(
    change_name: str,
    state: dict[str, Any],
    state_path: str,
    *,
    timeout_override: int | None = None,
    loop_threshold: int = WATCHDOG_LOOP_THRESHOLD,
    event_bus: Any = None,
) -> WatchdogResult:
    """Main watchdog check for a single change.

    Detects: timeouts (per-state), action hash loops, and escalates accordingly.

    Args:
        change_name: Name of the change to check.
        state: Full orchestration state dict.
        state_path: Path to state JSON file.
        timeout_override: Override timeout from directives.
        loop_threshold: Consecutive same-hash count to trigger escalation.

    Returns:
        WatchdogResult with action and reason.
    """
    change = _find_change(state, change_name)
    if not change:
        return WatchdogResult(action="ok", reason="change not found")

    status = change.get("status", "")

    # Only watch active statuses
    if status not in ("running", "verifying", "dispatched", "stalled"):
        return WatchdogResult(action="ok", reason=f"status={status}, not watched")

    # Lazy-init watchdog state
    wd = change.get("watchdog")
    if not wd:
        wd = watchdog_init_state(change_name)
        change["watchdog"] = wd

    last_activity = wd.get("last_activity_epoch", 0)
    escalation_level = wd.get("escalation_level", 0)
    consecutive_same = wd.get("consecutive_same_hash", 0)
    now = int(time.time())

    # Check for activity (resets escalation)
    if _has_activity(change, last_activity):
        if escalation_level > 0:
            logger.info(
                "Watchdog: %s recovered — resetting escalation from level %d",
                change_name,
                escalation_level,
            )
        _update_watchdog_state(wd, now, 0, 0)
        return WatchdogResult(action="ok", reason="activity detected, reset")

    # Artifact creation grace: skip hash detection if loop-state.json absent
    wt_path = change.get("worktree_path", "")
    if wt_path and not Path(wt_path, ".set", "loop-state.json").is_file():
        return WatchdogResult(
            action="ok", reason="artifact creation phase, no loop-state yet"
        )

    # Action hash loop detection
    current_hash = _compute_action_hash(change, state_path)
    hash_ring = wd.get("action_hash_ring", [])
    prev_hash = hash_ring[-1] if hash_ring else ""

    if current_hash == prev_hash and current_hash:
        consecutive_same += 1
    else:
        consecutive_same = 0

    # Update ring buffer
    hash_ring.append(current_hash)
    if len(hash_ring) > WATCHDOG_HASH_RING_SIZE:
        hash_ring = hash_ring[-WATCHDOG_HASH_RING_SIZE:]
    wd["action_hash_ring"] = hash_ring
    wd["consecutive_same_hash"] = consecutive_same

    # Timeout check
    timeout_secs = _timeout_for_status(status, timeout_override)
    idle_secs = now - last_activity

    should_escalate = False

    # Fast-path: running change with null/zero PID → immediate escalation
    if status == "running" and not change.get("ralph_pid"):
        logger.warning(
            "Watchdog: %s running with invalid ralph_pid=%s — immediate escalation",
            change_name,
            change.get("ralph_pid"),
        )
        escalation_level += 1
        _update_watchdog_state(wd, now, escalation_level, consecutive_same)
        action = _escalation_action(escalation_level)
        return WatchdogResult(
            action=action,
            reason=f"running with null/zero PID (ralph_pid={change.get('ralph_pid')})",
            escalation_level=escalation_level,
        )

    # Loop detection triggers escalation (but only if Ralph PID is dead)
    if consecutive_same >= loop_threshold:
        ralph_pid = change.get("ralph_pid", 0)
        if ralph_pid and _is_pid_alive(ralph_pid):
            if consecutive_same == loop_threshold or consecutive_same % 20 == 0:
                logger.debug(
                    "Watchdog: %s hash loop (%d identical) but PID %d alive — skipping",
                    change_name,
                    consecutive_same,
                    ralph_pid,
                )
            return WatchdogResult(
                action="warn",
                reason=f"hash_loop_pid_alive ({consecutive_same} identical)",
                escalation_level=escalation_level,
            )
        else:
            logger.warning(
                "Watchdog: %s stuck in loop (%d identical hashes, PID %s dead)",
                change_name,
                consecutive_same,
                ralph_pid,
            )
            should_escalate = True

    # Timeout triggers escalation (but only if Ralph PID is dead)
    if idle_secs >= timeout_secs:
        ralph_pid = change.get("ralph_pid", 0)
        if ralph_pid and _is_pid_alive(ralph_pid):
            return WatchdogResult(
                action="ok",
                reason=f"timeout ({idle_secs}s) but PID {ralph_pid} alive",
            )
        logger.warning(
            "Watchdog: %s timeout (%ds idle, threshold %ds)",
            change_name,
            idle_secs,
            timeout_secs,
        )
        should_escalate = True

    if should_escalate:
        old_level = escalation_level
        escalation_level += 1
        _update_watchdog_state(wd, now, escalation_level, consecutive_same)
        action = _escalation_action(escalation_level)
        logger.info("Watchdog escalation: %s level %d → %d, action=%s",
                     change_name, old_level, escalation_level, action)
        if event_bus:
            event_bus.emit("WATCHDOG_ESCALATION", change=change_name, data={
                "from_level": old_level,
                "to_level": escalation_level,
                "action": action,
            })
        return WatchdogResult(
            action=action,
            reason=f"escalation level {escalation_level}",
            escalation_level=escalation_level,
        )

    return WatchdogResult(action="ok", reason="healthy")


# ─── Idle Detection ──────────────────────────────────────────────


def check_idle(
    state: dict[str, Any],
    event_bus: Any = None,
) -> None:
    """Check if the entire orchestration is idle (no active changes).

    Emits IDLE_START when idle threshold exceeded, IDLE_END when activity resumes.
    """
    global _idle_active

    changes = state.get("changes", [])
    active_statuses = ("running", "verifying", "dispatched", "integrating")
    active_changes = [c.get("name", "") for c in changes if c.get("status") in active_statuses]

    if active_changes:
        if _idle_active:
            _idle_active = False
            if event_bus:
                event_bus.emit("IDLE_END", data={"resumed_changes": active_changes})
                logger.debug("Idle ended — active changes: %s", active_changes)
        return

    # No active changes — check how long we've been idle
    now = int(time.time())
    last_activity = 0
    for c in changes:
        wd = c.get("watchdog", {})
        epoch = wd.get("last_activity_epoch", 0)
        if epoch > last_activity:
            last_activity = epoch

    idle_secs = now - last_activity if last_activity else 0

    if idle_secs >= IDLE_THRESHOLD_SECONDS and not _idle_active:
        _idle_active = True
        watched = [c.get("name", "") for c in changes if c.get("status") not in ("merged", "failed", "skipped")]
        if event_bus:
            event_bus.emit("IDLE_START", data={"watched_changes": watched, "idle_seconds": idle_secs})
            logger.debug("Idle started — no active changes for %ds, watching: %s", idle_secs, watched)


# ─── Init State ──────────────────────────────────────────────────
# Migrated from: watchdog.sh:_watchdog_init()


def watchdog_init_state(change_name: str = "") -> dict[str, Any]:
    """Create initial watchdog state baseline.

    Args:
        change_name: Name of the change (for logging).

    Returns:
        Initial watchdog state dict.
    """
    now = int(time.time())
    return {
        "last_activity_epoch": now,
        "action_hash_ring": [],
        "consecutive_same_hash": 0,
        "escalation_level": 0,
        "progress_baseline": 0,
    }


# ─── Hash Loop Detection ────────────────────────────────────────
# Migrated from: watchdog.sh:detect_hash_loop()


def detect_hash_loop(
    hash_ring: list[str],
    threshold: int = WATCHDOG_LOOP_THRESHOLD,
) -> bool:
    """Check if last N hashes in ring are all identical.

    Args:
        hash_ring: List of recent action hashes.
        threshold: Number of consecutive same hashes required.

    Returns:
        True if loop detected.
    """
    if len(hash_ring) < threshold:
        return False

    tail = hash_ring[-threshold:]
    return len(set(tail)) == 1 and tail[0] != ""


# ─── Escalation Logic ───────────────────────────────────────────
# Migrated from: watchdog.sh:_watchdog_escalate()


def _escalation_action(level: int) -> str:
    """Map escalation level to action string.

    Level 1: warn — warning only
    Level 2: restart — resume the change's agent
    Level 3: redispatch — close worktree, create fresh, redispatch
    Level 4+: fail — mark change as failed
    """
    if level <= 1:
        return "warn"
    elif level == 2:
        return "restart"
    elif level == 3:
        return "redispatch"
    else:
        return "fail"


# ─── Progress-Based Trend Detection ─────────────────────────────
# Migrated from: watchdog.sh:_watchdog_check_progress()


def check_progress(
    change_name: str,
    change: dict[str, Any],
    progress_baseline: int = 0,
) -> str | None:
    """Detect spinning or stuck patterns from loop-state iterations.

    Args:
        change_name: Name of the change.
        change: Change dict from state.
        progress_baseline: Iteration number baseline (skip earlier iterations).

    Returns:
        "spinning", "stuck", or None (healthy).
    """
    wt_path = change.get("worktree_path", "")
    if not wt_path:
        return None

    loop_state_file = Path(wt_path) / ".claude" / "loop-state.json"
    if not loop_state_file.is_file():
        return None

    # Guard: skip if already failed/paused/waiting
    status = change.get("status", "")
    if status in ("failed", "paused", "waiting:budget"):
        return None

    try:
        loop_data = json.loads(loop_state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    # Skip if loop already done or waiting
    loop_status = loop_data.get("status", "unknown")
    if loop_status in ("done", "waiting:api"):
        return None

    iterations = loop_data.get("iterations", [])
    if len(iterations) < 2:
        return None

    # Filter to iterations after baseline and get tail 3
    tail = [i for i in iterations if i.get("n", 0) > progress_baseline][-3:]
    if len(tail) < 3:
        return None

    # Check if all tail iterations have empty commits
    all_no_commits = all(
        not i.get("commits") for i in tail
    )
    if not all_no_commits:
        return None  # Progress — recent commits exist

    # TOCTOU guard: re-read status
    try:
        recheck = json.loads(loop_state_file.read_text(encoding="utf-8"))
        if recheck.get("status") == "done":
            return None
    except (json.JSONDecodeError, OSError):
        pass

    # Determine pattern
    all_no_op = all(i.get("no_op") is True for i in tail)
    if all_no_op:
        logger.warning("Watchdog progress: %s spinning (3 consecutive no-op iterations)", change_name)
        return "spinning"
    else:
        logger.warning("Watchdog progress: %s stuck (3 iterations with no commits)", change_name)
        return "stuck"


# ─── Heartbeat ───────────────────────────────────────────────────
# Migrated from: watchdog.sh:watchdog_heartbeat()


def heartbeat_data(state: dict[str, Any]) -> dict[str, Any]:
    """Build heartbeat event data from state.

    Returns:
        Dict with active_changes count and active_seconds.
    """
    changes = state.get("changes", [])
    active = sum(
        1 for c in changes if c.get("status") in ("running", "verifying", "dispatched")
    )
    active_seconds = state.get("active_seconds", 0)
    return {"active_changes": active, "active_seconds": active_seconds}


# ─── Internal Helpers ────────────────────────────────────────────


def _find_change(state: dict[str, Any], name: str) -> dict[str, Any] | None:
    """Find a change by name in state."""
    for c in state.get("changes", []):
        if c.get("name") == name:
            return c
    return None


def _has_activity(change: dict[str, Any], last_epoch: int) -> bool:
    """Check if there's been activity since last_epoch.

    Migrated from: watchdog.sh:_watchdog_has_activity()
    """
    wt_path = change.get("worktree_path", "")
    if not wt_path:
        return False

    loop_state = Path(wt_path) / ".claude" / "loop-state.json"
    if loop_state.is_file():
        try:
            mtime = int(loop_state.stat().st_mtime)
            if mtime > last_epoch:
                return True
        except OSError:
            pass

    return False


def _compute_action_hash(change: dict[str, Any], state_path: str) -> str:
    """Compute action hash from loop-state mtime, tokens, and ralph status.

    Migrated from: watchdog.sh:_watchdog_action_hash()
    """
    wt_path = change.get("worktree_path", "")
    loop_state = Path(wt_path, ".set", "loop-state.json") if wt_path else Path(".")

    mtime = "0"
    ralph_status = "unknown"
    if loop_state.is_file():
        try:
            mtime = str(int(loop_state.stat().st_mtime))
        except OSError:
            pass
        try:
            ls_data = json.loads(loop_state.read_text(encoding="utf-8"))
            ralph_status = ls_data.get("status", "unknown")
        except (json.JSONDecodeError, OSError):
            pass

    tokens = str(change.get("tokens_used", 0))
    raw = f"{mtime}:{tokens}:{ralph_status}"
    h = hashlib.md5(raw.encode()).hexdigest()
    logger.debug("Watchdog hash: %s = %s (mtime=%s, tokens=%s, ralph=%s)",
                  change.get("name", "?"), h[:8], mtime, tokens, ralph_status)
    return h


def _timeout_for_status(
    status: str,
    override: int | None = None,
) -> int:
    """Get timeout threshold for a given change status.

    Migrated from: watchdog.sh:_watchdog_timeout_for_status()
    """
    if override:
        return override
    return {
        "running": WATCHDOG_TIMEOUT_RUNNING,
        "verifying": WATCHDOG_TIMEOUT_VERIFYING,
        "dispatched": WATCHDOG_TIMEOUT_DISPATCHED,
    }.get(status, WATCHDOG_TIMEOUT_RUNNING)


def _update_watchdog_state(
    wd: dict[str, Any],
    activity_epoch: int,
    escalation_level: int,
    consecutive_same: int,
) -> None:
    """Update watchdog state dict in-place.

    Migrated from: watchdog.sh:_watchdog_update()
    """
    wd["last_activity_epoch"] = activity_epoch
    wd["escalation_level"] = escalation_level
    wd["consecutive_same_hash"] = consecutive_same


def _is_pid_alive(pid: int) -> bool:
    """Check if a PID is alive."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False
