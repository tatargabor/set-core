"""Main orchestration monitoring loop (engine).

Migrated from: lib/orchestration/monitor.sh (586 lines)
Source line comments reference the original bash function names.

Functions:
    monitor_loop       — main while-loop: poll, dispatch, merge, replan, watchdog
    parse_directives   — JSON to Directives dataclass
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .root import SET_TOOLS_ROOT
from .state import (
    OrchestratorState,
    load_state,
    locked_state,
    update_change_field,
    update_state_field,
)
from .subprocess_utils import run_command

logger = logging.getLogger(__name__)

# ─── Constants (from bash globals) ──────────────────────────────────

DEFAULT_POLL_INTERVAL = 15
DEFAULT_TIME_LIMIT = 0  # 0 = no limit; set "5h" or similar in config to enable
DEFAULT_TOKEN_HARD_LIMIT = 50_000_000
DEFAULT_MONITOR_IDLE_TIMEOUT = 1800
DEFAULT_MAX_REPLAN_RETRIES = 3
MAX_REPLAN_CYCLES = 5
VERIFY_TIMEOUT = 600  # 10 min max for verify gate


# ─── Directives ────────────────────────────────────────────────────

@dataclass
class Directives:
    """Parsed orchestration directives from JSON input.

    Mirrors the ~40 variables parsed from JSON in monitor.sh L5-106.
    """

    max_parallel: int = 1  # Sequential execution; >1 is experimental (merge conflicts, port collisions)
    checkpoint_every: int = 0
    test_command: str = ""
    merge_policy: str = "eager"
    token_budget: int = 0
    auto_replan: bool = False
    max_replan_cycles: int = MAX_REPLAN_CYCLES
    test_timeout: int = 300
    max_verify_retries: int = 3
    e2e_retry_limit: int = 3
    review_before_merge: bool = True
    review_model: str = "opus"
    default_model: str = "opus"
    smoke_command: str = ""
    smoke_timeout: int = 120
    smoke_blocking: bool = False
    smoke_fix_token_budget: int = 0
    smoke_fix_max_turns: int = 15
    smoke_fix_max_retries: int = 3
    smoke_health_check_url: str = ""
    smoke_health_check_timeout: int = 30
    e2e_command: str = ""
    e2e_timeout: int = 120
    e2e_mode: str = "per_change"
    e2e_port_base: int = 3100
    token_hard_limit: int = DEFAULT_TOKEN_HARD_LIMIT
    events_log: bool = True
    events_max_size: int = 1048576
    watchdog_timeout: int = 0
    watchdog_loop_threshold: int = 0
    max_redispatch: int = 2
    context_pruning: bool = True
    model_routing: str = "off"
    team_mode: bool = False
    post_phase_audit: bool = True
    milestones_enabled: bool = False
    milestones_dev_server: str = ""
    milestones_base_port: int = 3100
    milestones_max_worktrees: int = 3
    checkpoint_auto_approve: bool = False
    checkpoint_timeout: int = 0
    post_merge_command: str = ""
    monitor_idle_timeout: int = DEFAULT_MONITOR_IDLE_TIMEOUT
    time_limit_secs: int = 0

    # Hook scripts
    hook_pre_dispatch: str = ""
    hook_post_verify: str = ""
    hook_pre_merge: str = ""
    hook_post_merge: str = ""
    hook_on_fail: str = ""


def parse_directives(raw: dict) -> Directives:
    """Parse JSON directives dict into Directives dataclass.

    Source: monitor.sh L5-106 (all the jq -r '.field // default' calls)
    """
    d = Directives()
    d.max_parallel = _int(raw, "max_parallel", d.max_parallel)
    d.checkpoint_every = _int(raw, "checkpoint_every", d.checkpoint_every)
    d.test_command = _str(raw, "test_command", d.test_command)
    d.merge_policy = _str(raw, "merge_policy", d.merge_policy)
    d.token_budget = _int(raw, "token_budget", d.token_budget)
    d.auto_replan = _bool(raw, "auto_replan", d.auto_replan)
    d.max_replan_cycles = _int(raw, "max_replan_cycles", d.max_replan_cycles)
    d.e2e_retry_limit = _int(raw, "e2e_retry_limit", d.e2e_retry_limit)
    d.test_timeout = _int(raw, "test_timeout", d.test_timeout)
    d.max_verify_retries = _int(raw, "max_verify_retries", d.max_verify_retries)
    d.review_before_merge = _bool(raw, "review_before_merge", d.review_before_merge)
    d.review_model = _str(raw, "review_model", d.review_model)
    d.default_model = _str(raw, "default_model", d.default_model)
    d.smoke_command = _str(raw, "smoke_command", d.smoke_command)
    d.smoke_timeout = _int(raw, "smoke_timeout", d.smoke_timeout)
    d.smoke_blocking = _bool(raw, "smoke_blocking", d.smoke_blocking)
    d.smoke_fix_token_budget = _int(raw, "smoke_fix_token_budget", d.smoke_fix_token_budget)
    d.smoke_fix_max_turns = _int(raw, "smoke_fix_max_turns", d.smoke_fix_max_turns)
    d.smoke_fix_max_retries = _int(raw, "smoke_fix_max_retries", d.smoke_fix_max_retries)
    d.smoke_health_check_url = _str(raw, "smoke_health_check_url", d.smoke_health_check_url)
    d.smoke_health_check_timeout = _int(raw, "smoke_health_check_timeout", d.smoke_health_check_timeout)
    d.e2e_command = _str(raw, "e2e_command", d.e2e_command)
    d.e2e_timeout = _int(raw, "e2e_timeout", d.e2e_timeout)
    d.e2e_mode = _str(raw, "e2e_mode", d.e2e_mode)
    d.e2e_port_base = _int(raw, "e2e_port_base", d.e2e_port_base)
    d.token_hard_limit = _int(raw, "token_hard_limit", d.token_hard_limit)
    d.events_log = _bool(raw, "events_log", d.events_log)
    d.events_max_size = _int(raw, "events_max_size", d.events_max_size)
    d.watchdog_timeout = _int(raw, "watchdog_timeout", d.watchdog_timeout)
    d.watchdog_loop_threshold = _int(raw, "watchdog_loop_threshold", d.watchdog_loop_threshold)
    d.max_redispatch = _int(raw, "max_redispatch", d.max_redispatch)
    d.context_pruning = _bool(raw, "context_pruning", d.context_pruning)
    d.model_routing = _str(raw, "model_routing", d.model_routing)
    d.team_mode = _bool(raw, "team_mode", d.team_mode)
    d.post_phase_audit = _bool(raw, "post_phase_audit", d.post_phase_audit)
    d.post_merge_command = _str(raw, "post_merge_command", d.post_merge_command)
    d.monitor_idle_timeout = _int(raw, "monitor_idle_timeout", d.monitor_idle_timeout)
    d.checkpoint_auto_approve = _bool(raw, "checkpoint_auto_approve", d.checkpoint_auto_approve)
    d.checkpoint_timeout = _int(raw, "checkpoint_timeout", d.checkpoint_timeout)

    # Milestones sub-object
    ms = raw.get("milestones", {})
    if isinstance(ms, dict):
        d.milestones_enabled = _bool(ms, "enabled", d.milestones_enabled)
        d.milestones_dev_server = _str(ms, "dev_server", d.milestones_dev_server)
        d.milestones_base_port = _int(ms, "base_port", d.milestones_base_port)
        d.milestones_max_worktrees = _int(ms, "max_worktrees", d.milestones_max_worktrees)

    # Hooks
    d.hook_pre_dispatch = _str(raw, "hook_pre_dispatch", d.hook_pre_dispatch)
    d.hook_post_verify = _str(raw, "hook_post_verify", d.hook_post_verify)
    d.hook_pre_merge = _str(raw, "hook_pre_merge", d.hook_pre_merge)
    d.hook_post_merge = _str(raw, "hook_post_merge", d.hook_post_merge)
    d.hook_on_fail = _str(raw, "hook_on_fail", d.hook_on_fail)

    # Parse time limit
    tl = raw.get("time_limit", DEFAULT_TIME_LIMIT)
    if isinstance(tl, str) and tl not in ("none", "0", ""):
        from .config import parse_duration
        d.time_limit_secs = parse_duration(tl)
    elif isinstance(tl, (int, float)):
        d.time_limit_secs = int(tl)

    return d


# ─── Cleanup / Shutdown ────────────────────────────────────────────

# Guard: only the monitor that acquired the lock should modify state on exit.
# Set to True inside monitor_loop() after lock acquisition succeeds.
_orchestrator_lock_held = False


def _emit_event(state_file: str, event_type: str, change: str = "", data: dict | None = None) -> None:
    """Append a JSONL event to the orchestration events log."""
    events_path = state_file.replace(".json", "-events.jsonl")
    line = json.dumps({
        "ts": datetime.now().astimezone().isoformat(),
        "type": event_type,
        **({"change": change} if change else {}),
        "data": data or {},
    })
    try:
        with open(events_path, "a") as f:
            f.write(line + "\n")
    except OSError:
        logger.warning("Failed to write event %s", event_type)


def _graceful_shutdown_ralph_pids(state_file: str, state: OrchestratorState, timeout: int = 90) -> None:
    """Send SIGTERM to all active Ralph PIDs, wait with progress events, SIGKILL stragglers."""
    import signal as sig

    active_changes = [c for c in state.changes if c.status in ("running", "dispatched", "verifying") and c.ralph_pid]
    if not active_changes:
        return

    _emit_event(state_file, "SHUTDOWN_STARTED", data={
        "changes": [c.name for c in active_changes],
    })

    # Send SIGTERM to each Ralph PID
    live_pids: dict[int, str] = {}  # pid -> change_name
    for c in active_changes:
        pid = c.ralph_pid
        _emit_event(state_file, "CHANGE_STOPPING", change=c.name, data={"ralph_pid": pid})
        try:
            os.kill(pid, sig.SIGTERM)
            live_pids[pid] = c.name
            logger.info("Sent SIGTERM to Ralph PID %d (%s)", pid, c.name)
        except (OSError, ProcessLookupError):
            # Already dead
            _emit_event(state_file, "CHANGE_STOPPED", change=c.name, data={"ralph_pid": pid, "exit_code": -1, "duration_ms": 0})
            logger.info("Ralph PID %d (%s) already dead", pid, c.name)

    # Wait for PIDs to exit (up to timeout)
    start_wait = time.time()
    stop_times: dict[str, float] = {}
    while live_pids and (time.time() - start_wait) < timeout:
        for pid in list(live_pids):
            try:
                os.kill(pid, 0)  # Check if alive
            except (OSError, ProcessLookupError):
                name = live_pids.pop(pid)
                elapsed_ms = int((time.time() - start_wait) * 1000)
                stop_times[name] = elapsed_ms
                _emit_event(state_file, "CHANGE_STOPPED", change=name, data={"ralph_pid": pid, "exit_code": 0, "duration_ms": elapsed_ms})
                logger.info("Ralph PID %d (%s) stopped after %dms", pid, name, elapsed_ms)
        if live_pids:
            time.sleep(1)

    # SIGKILL stragglers
    for pid, name in live_pids.items():
        try:
            os.kill(pid, sig.SIGKILL)
            elapsed_ms = int((time.time() - start_wait) * 1000)
            _emit_event(state_file, "CHANGE_STOPPED", change=name, data={"ralph_pid": pid, "exit_code": -9, "duration_ms": elapsed_ms, "forced": True})
            logger.warning("Force-killed Ralph PID %d (%s) after %ds timeout", pid, name, timeout)
        except (OSError, ProcessLookupError):
            pass

    # Set stopped changes to "paused" so they resume on restart
    for c in active_changes:
        try:
            update_change_field(state_file, c.name, "status", "paused")
        except Exception:
            logger.warning("Failed to set %s to paused", c.name)

    total_ms = int((time.time() - start_wait) * 1000)
    _emit_event(state_file, "SHUTDOWN_COMPLETE", data={"total_duration_ms": total_ms})


def cleanup_orchestrator(state_file: str, directives: Directives | None = None) -> None:
    """Cleanup on orchestrator exit: update state, kill dev servers, pause if needed.

    Called via atexit or signal handlers.

    Args:
        state_file: Path to orchestration state file.
        directives: Parsed directives (optional, for pause_on_exit check).
    """
    # If this process never acquired the orchestrator lock, don't touch state.
    # This prevents duplicate monitors (that failed lock acquisition) from
    # poisoning state with "stopped" when they exit.
    if not _orchestrator_lock_held:
        logger.info("Cleanup skipped — this process does not hold the orchestrator lock")
        return

    try:
        state = load_state(state_file)

        # Don't overwrite terminal states
        if state.status not in ("done", "time_limit"):
            update_state_field(state_file, "status", "stopped")
            logger.info("Orchestrator state set to 'stopped'")

        # Graceful shutdown: SIGTERM all active Ralph PIDs, wait, then SIGKILL
        _graceful_shutdown_ralph_pids(state_file, state)

        # Kill auto-started dev server PIDs
        dev_pids = state.extras.get("dev_server_pids", [])
        if dev_pids:
            import signal as sig
            for pid in dev_pids:
                try:
                    os.kill(pid, sig.SIGTERM)
                    logger.info("Killed dev server PID %d", pid)
                except (OSError, ProcessLookupError):
                    pass

        # Generate final report
        _generate_report_safe(state_file)
        _generate_review_findings_summary_safe(state_file)
        _persist_run_learnings(state_file)

    except Exception:
        logger.error("cleanup_orchestrator failed", exc_info=True)


# ─── Monitor Loop ──────────────────────────────────────────────────

# Source: monitor.sh monitor_loop() L5-586
def monitor_loop(
    directives_json: str,
    state_file: str,
    *,
    poll_interval: int = DEFAULT_POLL_INTERVAL,
    event_bus: Any = None,
    checkpoint_auto_approve: bool = False,
    checkpoint_timeout: int = 0,
) -> None:
    """Run the main orchestration monitoring loop.

    This is the Python equivalent of monitor.sh monitor_loop().
    Parses directives, then loops: poll → dispatch → merge → replan → watchdog.
    """
    # Set up file logging for the monitor process
    from .logging_config import setup_logging
    setup_logging()

    # Single-instance guard: flock on orchestrator lock file
    import fcntl
    lock_path = os.path.join(os.path.dirname(state_file) or ".", "orchestrator.lock")
    lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        # Check if the lock holder is still alive (LOCK-002)
        stale = False
        try:
            with open(lock_path) as f:
                pid_str = f.read().strip()
            if pid_str:
                holder_pid = int(pid_str)
                try:
                    os.kill(holder_pid, 0)
                except OSError:
                    stale = True
                    logger.warning("Stale orchestrator lock (PID %d dead) — recovering", holder_pid)
        except (ValueError, OSError):
            stale = True
            logger.warning("Unreadable orchestrator lock — recovering")

        if stale:
            lock_fd.close()
            os.unlink(lock_path)
            lock_fd = open(lock_path, "w")
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            logger.error("Another orchestrator is already running — exiting")
            lock_fd.close()
            return

    # Write PID for liveness checks (LOCK-002)
    lock_fd.write(str(os.getpid()))
    lock_fd.flush()
    logger.info("Acquired orchestrator lock: %s (PID %d)", lock_path, os.getpid())

    # Mark that this process holds the lock — enables cleanup_orchestrator
    global _orchestrator_lock_held
    _orchestrator_lock_held = True

    # Parse directives — try file path, then JSON string, then state fallback
    raw = None
    if os.path.isfile(directives_json):
        with open(directives_json) as f:
            raw = json.load(f)
    else:
        try:
            raw = json.loads(directives_json)
        except (json.JSONDecodeError, ValueError):
            # Temp file was deleted between restarts — fall back to persisted directives
            logger.warning(
                "Directives not found at %s — loading from state file", directives_json
            )
            state_for_directives = load_state(state_file)
            raw = state_for_directives.extras.get("directives")
            if raw is None:
                logger.error("No directives in state file either — cannot continue")
                return

    d = parse_directives(raw)

    # Register atexit cleanup AFTER lock + directives parsed — prevents duplicate
    # monitors (that fail lock acquisition) from setting status=stopped on exit
    import atexit
    atexit.register(cleanup_orchestrator, state_file, d)

    # Load plugin orchestration directives
    try:
        from .profile_loader import load_profile, NullProfile
        profile = load_profile()
        if not isinstance(profile, NullProfile):
            plugin_directives = profile.get_orchestration_directives()
            if plugin_directives:
                logger.info(
                    "Loaded %d plugin orchestration directive(s)", len(plugin_directives)
                )
                # Store on directives object for dispatch/post-merge to use
                if not hasattr(d, "plugin_directives"):
                    d.plugin_directives = []
                d.plugin_directives = list(plugin_directives)
    except Exception:
        logger.debug("Plugin directive loading failed (non-critical)", exc_info=True)

    # Apply CLI overrides
    if checkpoint_auto_approve:
        d.checkpoint_auto_approve = True
    if checkpoint_timeout:
        d.checkpoint_timeout = checkpoint_timeout

    # Persist timing info and orchestrator PID
    start_epoch = int(time.time())
    update_state_field(state_file, "started_epoch", start_epoch)
    update_state_field(state_file, "time_limit_secs", d.time_limit_secs)
    update_state_field(state_file, "orchestrator_pid", os.getpid())

    # Restore active_seconds from state (cumulative across restarts)
    state = load_state(state_file)
    active_seconds = state.extras.get("active_seconds", 0)
    token_wait = False
    replan_retry_count = 0

    # Ensure state is "running" — the bash layer may have set "stopped"
    # via EXIT trap before exec'ing to us
    if state.status == "stopped":
        logger.info("Resuming orchestration (was: stopped)")
        update_state_field(state_file, "status", "running")
    elif state.status == "checkpoint":
        logger.info("Stale checkpoint cleared on restart — resuming")
        update_state_field(state_file, "status", "running")

    # Clear checkpoint-specific transient state on restart
    _clear_checkpoint_state(state_file)

    logger.info("Monitor loop started (poll every %ds, auto_replan=%s)", poll_interval, d.auto_replan)

    # Self-watchdog tracking
    last_progress_ts = int(time.time())
    idle_escalation_count = 0

    poll_count = 0

    while True:
        time.sleep(poll_interval)
        poll_count += 1

        # Track active time
        if not token_wait and _any_loop_active(state_file):
            active_seconds += poll_interval
            update_state_field(state_file, "active_seconds", active_seconds)

        # Check time limit
        if d.time_limit_secs > 0 and active_seconds >= d.time_limit_secs:
            wall_elapsed = int(time.time()) - start_epoch
            logger.warning(
                "Time limit reached (%ds active, %ds wall clock)",
                active_seconds, wall_elapsed,
            )
            update_state_field(state_file, "status", "time_limit")
            _send_terminal_notifications(state_file, "time_limit", event_bus)
            _generate_report_safe(state_file)
            _generate_review_findings_summary_safe(state_file)
            _persist_run_learnings(state_file)
            break

        # Check external stop
        state = load_state(state_file)
        if state.status in ("stopped", "done"):
            _generate_report_safe(state_file)
            _generate_review_findings_summary_safe(state_file)
            _persist_run_learnings(state_file)
            break
        if state.status == "paused":
            continue

        # Poll active changes (running + verifying) — must run even
        # during checkpoint so dead Ralph processes are detected and
        # verify/merge can complete.
        poll_e2e_cmd = d.e2e_command if d.e2e_mode != "phase_end" else ""
        _signal_alive(state_file, event_bus)
        _poll_active_changes(state_file, d, poll_e2e_cmd, event_bus)
        _signal_alive(state_file, event_bus)

        # Safety net: check suspended changes
        _poll_suspended_changes(state_file, d, poll_e2e_cmd, event_bus)

        # During checkpoint, skip dispatch and advancement but still
        # allow completion detection and merge queue retries.
        if state.status == "checkpoint":
            _signal_alive(state_file, event_bus)
            _drain_merge_then_dispatch(state_file, d, event_bus)
            _signal_alive(state_file, event_bus)
            if _check_completion(state_file, d, event_bus):
                break
            if d.checkpoint_auto_approve:
                logger.info("Checkpoint auto-approved — resuming")
                update_state_field(state_file, "status", "running")
            elif _checkpoint_approved(state):
                logger.info("Checkpoint approved via API — resuming")
                update_state_field(state_file, "status", "running")
            elif d.checkpoint_timeout > 0:
                started = state.extras.get("checkpoint_started_at", 0)
                if started and (int(time.time()) - started) >= d.checkpoint_timeout:
                    elapsed = int(time.time()) - started
                    logger.warning(
                        "Checkpoint timed out after %ds — auto-resuming",
                        elapsed,
                    )
                    update_state_field(state_file, "status", "running")
                    if event_bus:
                        event_bus.emit(
                            "CHECKPOINT_TIMEOUT",
                            data={"elapsed": elapsed},
                        )
                else:
                    continue
            else:
                continue

        # Token budget enforcement
        if d.token_budget > 0:
            total_tokens = sum(c.tokens_used for c in load_state(state_file).changes)
            if total_tokens > d.token_budget:
                if not token_wait:
                    logger.warning("Token budget exceeded (%d > %d) — waiting", total_tokens, d.token_budget)
                    token_wait = True
                # Still drain merges while waiting for token budget
                _signal_alive(state_file, event_bus)
                _drain_merge_then_dispatch(state_file, d, event_bus)
                _signal_alive(state_file, event_bus)
                continue
            elif token_wait:
                logger.info("Token budget available — resuming dispatch")
                token_wait = False

        # Verify-failed recovery
        _recover_verify_failed(state_file, d, event_bus)

        # Integration e2e failed recovery (redispatch agent to fix)
        _recover_integration_e2e_failed(state_file, d, event_bus)

        # Note: no cascade_failed_deps() — pending changes with failed deps
        # simply stay pending (never dispatched because deps_met() returns False).
        # _check_all_done() and _check_phase_milestone() treat them as terminal.

        # Merge-before-dispatch serialization: if merge queue has items,
        # drain it completely before dispatching new changes. This ensures
        # archive commits are on main before new worktrees are created,
        # eliminating the archive race (Bug #38).
        state = load_state(state_file)
        pre_running = _count_by_status(state_file, "running")
        pre_merged = _count_by_status(state_file, "merged")

        _signal_alive(state_file, event_bus)
        if state.merge_queue:
            merged = _drain_merge_then_dispatch(state_file, d, event_bus)
        else:
            _dispatch_ready_safe(state_file, d, event_bus)
            merged = 0
        _signal_alive(state_file, event_bus)

        post_running = _count_by_status(state_file, "running")
        post_merged = _count_by_status(state_file, "merged")
        if post_running > pre_running or post_merged > pre_merged:
            last_progress_ts = int(time.time())
        elif post_running > 0:
            # Agents are actively running — treat as progress to prevent
            # self-watchdog from killing the orchestrator while agents are
            # still in artifact creation / initial setup (no commits yet).
            last_progress_ts = int(time.time())

        # Phase advancement (always) + optional milestone check
        _check_phase_completion(state_file, d, event_bus)

        # Recover dep-blocked changes whose deps are now merged
        _recover_dep_blocked_safe(state_file, event_bus)

        # Recover merge-blocked changes whose blocking issues are resolved
        _recover_merge_blocked_safe(state_file, event_bus)

        # Resume stalled changes
        _resume_stalled_safe(state_file, event_bus)

        # Retry merge-blocked changes (re-add to queue for fresh integration)
        _retry_merge_queue_safe(state_file, event_bus)

        # Retry failed builds
        _retry_failed_builds_safe(state_file, d, event_bus)

        # Token hard limit
        if d.token_hard_limit > 0:
            _check_token_hard_limit(state_file, d, event_bus)

        # Self-watchdog
        _self_watchdog(
            state_file, d, last_progress_ts,
            idle_escalation_count, event_bus,
        )
        idle_elapsed = int(time.time()) - last_progress_ts
        if idle_elapsed > d.monitor_idle_timeout:
            idle_escalation_count += 1
            last_progress_ts = int(time.time())
        else:
            idle_escalation_count = 0

        # Generate report
        _generate_report_safe(state_file)

        # Periodic memory operations (every ~10 polls ≈ 2.5 minutes)
        if poll_count % 10 == 0:
            _periodic_memory_ops_safe(state_file)

        # Watchdog heartbeat — must be more frequent than sentinel stuck timeout (180s)
        # Every 8th poll at 15s = 120s, well within the 180s threshold
        if event_bus and poll_count % 8 == 0:
            event_bus.emit("WATCHDOG_HEARTBEAT")

        # Checkpoint check
        if d.checkpoint_every > 0:
            state = load_state(state_file)
            if state.changes_since_checkpoint >= d.checkpoint_every:
                _trigger_checkpoint_safe(state_file, "periodic", event_bus)
                continue

        # Heartbeat log — ensures orchestration log mtime advances every poll
        # so the bash sentinel doesn't trigger false "no progress" watchdog alarms.
        state = load_state(state_file)
        total_changes = len(state.changes)
        running_count = sum(1 for c in state.changes if c.status == "running")
        logger.info(
            "monitor heartbeat: %d changes tracked, %d running (poll #%d)",
            total_changes, running_count, poll_count,
        )
        if event_bus:
            event_bus.emit(
                "MONITOR_HEARTBEAT",
                data={
                    "poll": poll_count,
                    "total": total_changes,
                    "running": running_count,
                },
            )

        # Completion detection
        if _check_completion(state_file, d, event_bus):
            break


# ─── Poll Helpers ──────────────────────────────────────────────────

def _verify_gates_already_passed(change: Any) -> bool:
    """Return True if all blocking verify gates have already passed.

    Used on monitor restart to detect changes in "verifying" status where the
    gates completed successfully but the monitor died before queuing the merge
    (Bug #5b). Any blocking gate result of "fail" or "critical" → False.
    A gate with no result (None) → False (gates haven't run yet).
    """
    _PASS_VALUES = {"pass", "skipped", "warn-fail"}
    _FAIL_VALUES = {"fail", "critical"}

    extras = change.extras or {}

    # Collect results from all gates — dataclass fields and extras.
    # Must check ALL blocking gates, not just a subset. Rules gate result
    # is not persisted (failure always sets status to verify-failed before
    # crash window), but e2e and spec_coverage ARE persisted to extras.
    gate_results = [
        change.test_result,
        change.build_result,
        change.review_result,
        extras.get("scope_check"),
        extras.get("e2e_result"),
        extras.get("spec_coverage_result"),
    ]

    # All checked gates must have a result (not None) and none can be a hard failure
    for result in gate_results:
        if result is None:
            return False
        if result in _FAIL_VALUES:
            return False
    return True


def _signal_alive(state_file: str, event_bus: Any) -> None:
    """Emit heartbeat + touch state file mtime to prevent false sentinel kills.

    Called before and after long-running operations (dispatch, merge, poll)
    to keep the sentinel's idle timer well under 180s.
    """
    if event_bus:
        try:
            event_bus.emit("WATCHDOG_HEARTBEAT")
        except Exception:
            pass
    try:
        os.utime(state_file, None)
    except OSError:
        logger.warning("_signal_alive: could not touch state file %s", state_file)


def _has_live_children(pid: int) -> bool:
    """Check if a process has any child processes via pgrep -P."""
    try:
        result = subprocess.run(
            ["pgrep", "-P", str(pid)],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _is_pid_alive(pid: int) -> bool:
    """Check if a PID exists."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _poll_active_changes(
    state_file: str, d: Directives, poll_e2e_cmd: str, event_bus: Any
) -> None:
    """Poll all running + verifying changes."""
    from .verifier import poll_change

    state = load_state(state_file)
    for change in state.changes:
        if change.status not in ("running", "verifying", "integrating"):
            continue

        # --- Worktree existence check ---
        wt_path = change.worktree_path or ""
        if wt_path and not os.path.isdir(wt_path):
            # Worktree was deleted (sentinel cleanup or manual).
            # Mark as done so it goes through merge queue WITH gates, not auto-merged.
            if change.status == "running":
                logger.warning(
                    "Worktree missing for %s (status=%s, path=%s) — marking done for merge queue (with gates)",
                    change.name, change.status, wt_path,
                )
                update_change_field(state_file, change.name, "status", "done")
                _resolve_issues_for_change(change.name)
            elif change.status in ("verifying", "integrating"):
                logger.warning(
                    "Worktree missing for %s (status=%s) — marking stalled",
                    change.name, change.status,
                )
                update_change_field(state_file, change.name, "status", "stalled")
            # Don't auto-merge — let merge queue handle with gates
            if event_bus:
                event_bus.emit("WORKTREE_MISSING", change=change.name,
                               data={"reason": "worktree_missing"})
            continue

        # --- Dead agent detection (running + verifying) ---
        ralph_pid = change.ralph_pid or 0

        # For "running" changes: check if agent loop died (idle/crashed)
        if change.status == "running" and wt_path:
            loop_state_path = os.path.join(wt_path, ".set", "loop-state.json")
            if ralph_pid > 0 and not _is_pid_alive(ralph_pid):
                # Agent process is dead — check loop-state for why
                ls_status = ""
                try:
                    if os.path.isfile(loop_state_path):
                        with open(loop_state_path) as f:
                            ls = json.load(f)
                        ls_status = ls.get("status", "")
                except (json.JSONDecodeError, OSError):
                    pass

                if ls_status == "done":
                    # Agent completed successfully — transition to done, not stalled
                    logger.info(
                        "Change %s: agent finished (loop_status=done) — marking done",
                        change.name,
                    )
                    update_change_field(state_file, change.name, "status", "done")
                    _set_step(state_file, change.name, "integrating", event_bus)
                    _resolve_issues_for_change(change.name)
                    if event_bus:
                        event_bus.emit("CHANGE_DONE", change=change.name)
                    continue

                logger.warning(
                    "Change %s running but agent dead (pid=%d, loop_status=%s) — marking stalled",
                    change.name, ralph_pid, ls_status or "unknown",
                )
                update_change_field(state_file, change.name, "status", "stalled")
                update_change_field(state_file, change.name, "stalled_at", int(time.time()))
                if event_bus:
                    event_bus.emit("CHANGE_STALLED", change=change.name,
                                   data={"reason": f"dead_running_agent_{ls_status or 'unknown'}"})
                continue

        if change.status == "verifying":
            # Check 1: verify timeout
            verifying_since = change.extras.get("verifying_since", 0) if change.extras else 0
            if verifying_since:
                elapsed = int(time.time()) - verifying_since
                if elapsed > VERIFY_TIMEOUT:
                    logger.warning(
                        "Change %s verify timeout (%ds > %ds) — marking stalled",
                        change.name, elapsed, VERIFY_TIMEOUT,
                    )
                    update_change_field(state_file, change.name, "status", "stalled")
                    update_change_field(state_file, change.name, "stalled_at", int(time.time()))
                    if event_bus:
                        event_bus.emit("CHANGE_STALLED", change=change.name,
                                       data={"reason": "verify_timeout"})
                    continue

            # Check 2: dead agent (PID dead or alive with no children)
            if ralph_pid > 0:
                pid_alive = _is_pid_alive(ralph_pid)
                if not pid_alive or (pid_alive and not _has_live_children(ralph_pid)):
                    reason = "dead_verify_agent"
                    logger.warning(
                        "Change %s verifying but agent dead (pid=%d, alive=%s, children=%s) — marking stalled",
                        change.name, ralph_pid, pid_alive,
                        "no" if pid_alive else "n/a",
                    )
                    update_change_field(state_file, change.name, "status", "stalled")
                    update_change_field(state_file, change.name, "stalled_at", int(time.time()))
                    if event_bus:
                        event_bus.emit("CHANGE_STALLED", change=change.name,
                                       data={"reason": reason})
                    continue

        # Fast-merge path: if change is "verifying" and all gates already passed,
        # the monitor likely died between verify completion and merge queuing (Bug #5b).
        # Queue it for merge directly instead of re-running the full verify gate.
        if change.status == "verifying" and _verify_gates_already_passed(change):
            logger.info(
                "Resume fast-merge: %s has all gates passed — adding to merge queue directly",
                change.name,
            )
            with locked_state(state_file) as s:
                if change.name not in s.merge_queue:
                    s.merge_queue.append(change.name)
            continue

        try:
            poll_change(
                change.name, state_file,
                test_command=d.test_command,
                merge_policy=d.merge_policy,
                test_timeout=d.test_timeout,
                max_verify_retries=d.max_verify_retries,
                review_before_merge=d.review_before_merge,
                review_model=d.review_model,
                smoke_command=d.smoke_command,
                smoke_timeout=d.smoke_timeout,
                e2e_command=poll_e2e_cmd,
                e2e_timeout=d.e2e_timeout,
                event_bus=event_bus,
                design_snapshot_dir=os.getcwd(),
            )
        except Exception:
            logger.warning("Poll failed for %s", change.name, exc_info=True)


def _poll_suspended_changes(
    state_file: str, d: Directives, poll_e2e_cmd: str, event_bus: Any
) -> None:
    """Check paused/waiting/done changes for completed loop-state."""
    # Source: monitor.sh L211-249
    from .verifier import poll_change

    state = load_state(state_file)
    for change in state.changes:
        if change.status not in ("paused", "waiting:budget", "budget_exceeded", "done", "stalled"):
            continue

        wt_path = change.worktree_path or ""

        # For "done" changes: check merge queue
        if change.status == "done":
            # Check retry limit before re-adding — don't infinitely re-queue exhausted changes
            retry_count = change.extras.get("merge_retry_count", 0)
            if retry_count >= 3:  # MAX_MERGE_RETRIES
                logger.warning(
                    "Monitor: orphaned 'done' change %s has exhausted merge retries (%d) — marking integration-failed",
                    change.name, retry_count,
                )
                update_change_field(state_file, change.name, "status", "integration-failed", event_bus=event_bus)
                if event_bus:
                    event_bus.emit("CHANGE_INTEGRATION_FAILED", change=change.name,
                                   data={"retry_count": retry_count, "reason": "orphaned_done_retry_exhausted"})
                continue
            if change.name not in state.merge_queue:
                logger.warning("Monitor: orphaned 'done' change %s — adding to merge queue", change.name)
                with locked_state(state_file) as st:
                    if change.name not in st.merge_queue:
                        st.merge_queue.append(change.name)
            continue

        # For "stalled" changes: check if loop-state shows done — recover if so
        if change.status == "stalled":
            if not wt_path:
                continue
            loop_state_path = os.path.join(wt_path, ".set", "loop-state.json")
            if os.path.isfile(loop_state_path):
                try:
                    with open(loop_state_path) as f:
                        ls = json.load(f)
                    if ls.get("status") == "done":
                        logger.info("Monitor: stalled change %s has loop-state=done — recovering to done", change.name)
                        update_change_field(state_file, change.name, "status", "done", event_bus=event_bus)
                        _resolve_issues_for_change(change.name)
                        with locked_state(state_file) as st:
                            if change.name not in st.merge_queue:
                                st.merge_queue.append(change.name)
                    # else: genuinely stalled — leave for manual intervention
                except Exception:
                    logger.debug("Failed to read loop-state for stalled change %s", change.name, exc_info=True)
            continue

        # Check loop-state for suspended changes
        if not wt_path:
            continue
        loop_state_path = os.path.join(wt_path, ".set", "loop-state.json")
        if not os.path.isfile(loop_state_path):
            continue

        try:
            with open(loop_state_path) as f:
                ls = json.load(f)
            if ls.get("status") == "done":
                logger.info("Monitor: suspended change %s has loop-state=done — processing", change.name)
                update_change_field(state_file, change.name, "status", "running")
                poll_change(
                    change.name, state_file,
                    test_command=d.test_command,
                    merge_policy=d.merge_policy,
                    test_timeout=d.test_timeout,
                    max_verify_retries=d.max_verify_retries,
                    review_before_merge=d.review_before_merge,
                    review_model=d.review_model,
                    smoke_command=d.smoke_command,
                    smoke_timeout=d.smoke_timeout,
                    e2e_command=poll_e2e_cmd,
                    e2e_timeout=d.e2e_timeout,
                    event_bus=event_bus,
                    design_snapshot_dir=os.getcwd(),
                )
        except Exception:
            logger.debug("Failed to parse loop-state for %s", change.name, exc_info=True)


# ─── Recovery ──────────────────────────────────────────────────────

def _recover_verify_failed(
    state_file: str, d: Directives, event_bus: Any
) -> None:
    """Resume verify-failed changes with retry context."""
    # Source: monitor.sh L274-306
    from .dispatcher import resume_change

    state = load_state(state_file)
    for change in state.changes:
        if change.status != "verify-failed":
            continue

        if change.verify_retry_count < d.max_verify_retries:
            # NOTE: Do NOT increment verify_retry_count here — handle_change_done
            # already incremented it before setting status to "verify-failed".
            # This recovery path runs only after crash between status write and
            # resume_change call. Double-incrementing would consume 2 retry slots.
            logger.info(
                "Recovering verify-failed %s (retry %d/%d)",
                change.name, change.verify_retry_count, d.max_verify_retries,
            )

            # Rebuild retry_context from stored build_output if missing
            retry_ctx = change.extras.get("retry_context", "")
            if not retry_ctx:
                build_output = change.extras.get("build_output", "")
                if build_output:
                    rebuild_prompt = (
                        f"Build failed after implementation. Fix the build errors.\n\n"
                        f"Build output (last 2000 chars):\n{build_output[-2000:]}\n\n"
                        f"Original scope: {change.scope}"
                    )
                    update_change_field(state_file, change.name, "retry_context", rebuild_prompt)

            resume_change(state_file, change.name)
        else:
            # Build failure reason from last available output
            reason = ""
            for output_key in ("build_output", "review_output", "test_output"):
                val = change.extras.get(output_key, "")
                if val:
                    reason = val[:500]
                    break
            logger.info("Verify-failed %s exhausted retries — marking failed (reason: %s)", change.name, reason[:100])
            update_change_field(state_file, change.name, "status", "failed")
            if reason:
                update_change_field(state_file, change.name, "failure_reason", reason)


def _set_step(state_file: str, change_name: str, step: str, event_bus: Any = None) -> None:
    """Set current lifecycle step and emit transition event."""
    update_change_field(state_file, change_name, "current_step", step)
    if event_bus:
        event_bus.emit("STEP_TRANSITION", change=change_name, data={"to": step})


def _parse_e2e_summary(output: str) -> dict:
    """Parse test runner summary output into structured results.

    Framework-agnostic: matches common patterns like 'N failed', 'N passed',
    and indented test lines with '[browser] › file:line › test name'.

    Returns {passed: int, failed: int, flaky: int, skipped: int, failing_tests: [str]}.
    """
    import re
    result: dict = {"passed": 0, "failed": 0, "flaky": 0, "skipped": 0, "failing_tests": []}

    for pat, key in [
        (r"(\d+)\s+passed", "passed"),
        (r"(\d+)\s+failed", "failed"),
        (r"(\d+)\s+flaky", "flaky"),
        (r"(\d+)\s+(?:did not run|skipped)", "skipped"),
    ]:
        m = re.search(pat, output)
        if m:
            result[key] = int(m.group(1))

    # Extract failing test names — matches indented lines after "N failed"
    # Format: "    [chromium] › tests/e2e/file.spec.ts:14:7 › Describe › test name"
    in_failed_section = False
    for line in output.split("\n"):
        stripped = line.strip()
        if re.match(r"\d+\s+failed", stripped):
            in_failed_section = True
            continue
        if in_failed_section:
            m = re.match(r"\[.*?\]\s+›\s+(.+)", stripped)
            if m:
                result["failing_tests"].append(m.group(1).strip())
            elif stripped and not stripped.startswith("["):
                in_failed_section = False  # Hit next section (e.g. "2 flaky")

    return result


def _classify_test_failures(wt_path: str, e2e_output: str) -> dict:
    """Classify E2E failures as own-change vs regression using git diff.

    Compares failing test file paths against files this change added/modified
    in tests/e2e/. Returns structured classification so the retry prompt
    gives the agent deterministic guidance (not an LLM judgment call).
    """
    import re

    # 1. Get test files THIS change added/modified vs main
    own_test_files: set[str] = set()
    try:
        r = run_command(
            ["git", "diff", "--name-only", "main..HEAD", "--", "tests/e2e/"],
            cwd=wt_path, timeout=10,
        )
        if r.exit_code == 0 and r.stdout.strip():
            own_test_files = {f.strip() for f in r.stdout.strip().splitlines()}
    except Exception:
        pass

    # 2. Parse failing tests
    parsed = _parse_e2e_summary(e2e_output)
    failing = parsed.get("failing_tests", [])

    # 3. Classify each failure
    own_failures: list[str] = []
    regression_failures: list[str] = []

    for test_line in failing:
        # Extract file path from test line: "tests/e2e/auth.spec.ts:70:7 › Desc › test"
        m = re.match(r"(tests/e2e/\S+?):\d+", test_line)
        if m:
            test_file = m.group(1)
            if test_file in own_test_files:
                own_failures.append(test_line)
            else:
                regression_failures.append(test_line)
        else:
            # Can't determine file — treat as own (safer)
            own_failures.append(test_line)

    return {
        "own_failures": own_failures,
        "regression_failures": regression_failures,
        "own_test_files": sorted(own_test_files),
    }


def _build_gate_retry_context(
    change: "ChangeState", wt_path: str, e2e_output: str
) -> str:
    """Build enriched retry context for gate-failed redispatch.

    Includes role framing, git history summary, parsed test results,
    raw test output, and original scope — so the agent immediately
    understands what it built and what needs fixing.
    """
    sections = [
        "Integration e2e tests failed after merging main into your branch. "
        "Fix the failing tests so they pass.\n"
    ]

    # --- Previous Work (git context) ---
    git_log = ""
    git_stat = ""
    last_commit_body = ""
    try:
        r = run_command(["git", "log", "--oneline", "main..HEAD"], cwd=wt_path, timeout=10)
        if r.exit_code == 0 and r.stdout.strip():
            lines = r.stdout.strip().splitlines()
            git_log = "\n".join(lines[:30])
            if len(lines) > 30:
                git_log += f"\n... and {len(lines) - 30} more commits"

        r = run_command(["git", "diff", "--stat", "main..HEAD"], cwd=wt_path, timeout=10)
        if r.exit_code == 0 and r.stdout.strip():
            lines = r.stdout.strip().splitlines()
            git_stat = "\n".join(lines[:50])
            if len(lines) > 50:
                git_stat += f"\n... and {len(lines) - 50} more files"

        r = run_command(["git", "log", "-1", "--format=%B"], cwd=wt_path, timeout=10)
        if r.exit_code == 0 and r.stdout.strip():
            last_commit_body = r.stdout.strip()
    except Exception:
        pass  # Fall back to no git context

    if git_log:
        sections.append(
            "## Your Previous Work\n\n"
            "You implemented this change and it's all committed in your working tree.\n\n"
            f"### Commits\n{git_log}\n\n"
            f"### Files Changed\n{git_stat}\n"
        )
        if last_commit_body and len(last_commit_body) > 50:
            sections.append(f"### Last Commit Summary\n{last_commit_body}\n")

    # --- Classified Test Results ---
    parsed = _parse_e2e_summary(e2e_output)
    classified = _classify_test_failures(wt_path, e2e_output)
    total = parsed["passed"] + parsed["failed"] + parsed["flaky"] + parsed["skipped"]
    if total > 0:
        summary = f"**{parsed['passed']} passed, {parsed['failed']} failed"
        if parsed["flaky"]:
            summary += f", {parsed['flaky']} flaky"
        if parsed["skipped"]:
            summary += f", {parsed['skipped']} did not run"
        summary += f"** out of {total} tests."

        sections.append(f"## Test Results\n\n{summary}\n")

        if classified["own_failures"]:
            own = "\n".join(f"- {t}" for t in classified["own_failures"])
            sections.append(
                f"### Your Test Failures (fix your test code or your app code)\n{own}\n"
            )

        if classified["regression_failures"]:
            reg = "\n".join(f"- {t}" for t in classified["regression_failures"])
            sections.append(
                f"### Regression Failures (your change broke a previously-passing test — fix YOUR app code, do NOT modify the old test)\n{reg}\n"
            )

    # --- Raw E2E Output ---
    if e2e_output:
        sections.append(
            f"### Test Output (last 2000 chars)\n{e2e_output[-2000:]}\n"
        )

    # --- Original Scope (reference) ---
    if change.scope:
        sections.append(f"## Original Scope\n{change.scope}\n")

    return "\n".join(sections)


def _recover_integration_e2e_failed(
    state_file: str, d: Directives, event_bus: Any
) -> None:
    """Redispatch agent to fix integration e2e failures."""
    from .dispatcher import resume_change

    state = load_state(state_file)
    for change in state.changes:
        if change.status != "integration-e2e-failed":
            continue

        wt_path = change.worktree_path or ""
        if not wt_path or not os.path.isdir(wt_path):
            logger.warning(
                "Integration e2e redispatch: worktree missing for %s — marking merge-blocked",
                change.name,
            )
            update_change_field(state_file, change.name, "status", "merge-blocked")
            continue

        # Build enriched retry_context with git history + parsed test results
        retry_ctx = change.extras.get("retry_context", "")
        if not retry_ctx:
            e2e_output = change.extras.get("integration_e2e_output", "")
            retry_ctx = _build_gate_retry_context(change, wt_path, e2e_output)
            update_change_field(state_file, change.name, "retry_context", retry_ctx)

        e2e_retry = change.extras.get("integration_e2e_retry_count", 0)
        logger.info(
            "Redispatching %s to fix integration e2e failures (attempt %d/2)",
            change.name, e2e_retry,
        )
        if event_bus:
            event_bus.emit("CHANGE_REDISPATCH", change=change.name,
                           data={"reason": "integration_e2e_failed", "retry": e2e_retry})

        resume_change(state_file, change.name, event_bus=event_bus)


# ─── Completion Detection ──────────────────────────────────────────

def _check_completion(
    state_file: str, d: Directives, event_bus: Any
) -> bool:
    """Check if all changes are terminal. Returns True if loop should exit."""
    # Source: monitor.sh L428-583
    state = load_state(state_file)
    total = len(state.changes)
    if total == 0:
        return False

    # Guard: don't exit while merge queue has unmerged changes.
    # A merge exception can leave changes in "done" status (gates passed but
    # not yet merged) — exiting now would lose them.
    if state.merge_queue:
        return False

    truly_complete = sum(
        1 for c in state.changes
        if c.status in ("done", "merged", "skipped")
    )
    failed_count = sum(1 for c in state.changes if c.status in ("failed", "integration-failed"))
    merge_blocked = sum(1 for c in state.changes if c.status == "merge-blocked")
    # Pending changes with all deps failed will never run — count as blocked, not active
    from .state import deps_failed
    blocked_pending = sum(
        1 for c in state.changes
        if c.status == "pending" and deps_failed(state, c.name)
    )
    active_count = sum(
        1 for c in state.changes
        if c.status in ("running", "pending", "verifying", "stalled")
    ) - blocked_pending

    # Partial completion: no active changes, some failed/blocked
    all_resolved = truly_complete + failed_count + merge_blocked + blocked_pending
    if active_count == 0 and truly_complete < total:
        if all_resolved >= total:
            logger.info(
                "%d succeeded, %d failed, %d merge-blocked, %d dep-blocked — all resolved",
                truly_complete, failed_count, merge_blocked, blocked_pending,
            )

    if truly_complete < total and not (active_count == 0 and all_resolved >= total):
        return False

    # Reconcile coverage before any terminal decision — fix stale entries
    # from requirements whose changes merged but coverage wasn't updated
    # (e.g. after sentinel partial reset)
    try:
        from .digest import reconcile_coverage, DIGEST_DIR
        fixed = reconcile_coverage(state_file, DIGEST_DIR)
        if fixed:
            logger.warning("Reconciled %d coverage entries before completion check", fixed)
    except Exception:
        logger.warning("Coverage reconciliation failed", exc_info=True)

    logger.info("All %d changes resolved (%d complete, %d dep-blocked)", total, truly_complete, blocked_pending)

    # Dep-blocked: some changes couldn't run because dependencies failed.
    # Stop with "stopped" status so user can fix failed changes and restart.
    if blocked_pending > 0:
        logger.info(
            "%d changes blocked by failed dependencies — stopping (not done)",
            blocked_pending,
        )
        update_state_field(state_file, "status", "stopped")
        update_state_field(state_file, "stop_reason", "dep_blocked")
        update_state_field(state_file, "dep_blocked_count", blocked_pending)
        _send_terminal_notifications(state_file, "dep_blocked", event_bus)
        _generate_report_safe(state_file)
        return True

    # Total failure: all changes failed, none succeeded — don't replan
    # (nothing was merged, so there's no foundation to build on)
    if truly_complete == 0 and failed_count > 0:
        logger.info(
            "Total failure: 0/%d succeeded — skipping replan, marking done",
            total,
        )
        update_state_field(state_file, "status", "done")
        update_state_field(state_file, "all_failed", True)
        from .merger import cleanup_all_worktrees
        cleanup_all_worktrees(state_file)
        _send_terminal_notifications(state_file, "total_failure", event_bus)
        _generate_report_safe(state_file)
        _generate_review_findings_summary_safe(state_file)
        _persist_run_learnings(state_file)
        return True

    # Phase-end E2E
    if d.e2e_mode == "phase_end" and d.e2e_command and truly_complete > 0:
        from .verifier import run_phase_end_e2e
        run_phase_end_e2e(d.e2e_command, state_file, e2e_timeout=d.e2e_timeout, event_bus=event_bus)

    # Auto-replan gate: skip if all succeeded and coverage is 100%
    if d.auto_replan:
        if failed_count == 0 and _all_coverage_merged():
            logger.info("All %d changes succeeded and coverage is 100%% — skipping replan", total)
        else:
            return _handle_auto_replan(state_file, d, event_bus)

    # Non-replan completion
    update_state_field(state_file, "status", "done")
    from .merger import cleanup_all_worktrees
    cleanup_all_worktrees(state_file)
    run_command(["git", "tag", "-f", "orch/complete", "HEAD"], timeout=10)
    _send_terminal_notifications(state_file, "done", event_bus)
    _generate_report_safe(state_file)
    _generate_review_findings_summary_safe(state_file)
    _persist_run_learnings(state_file)
    return True


def _handle_auto_replan(
    state_file: str, d: Directives, event_bus: Any
) -> bool:
    """Handle auto-replan cycle. Returns True if loop should exit.

    Fully Python implementation — no bash shell-out.
    Calls planner.collect_replan_context() and planner.build_decomposition_context()
    directly, then invokes Claude for a new plan.
    """
    state = load_state(state_file)
    cycle = state.extras.get("replan_cycle", 0)

    if cycle >= d.max_replan_cycles:
        logger.info("Replan cycle limit reached (%d/%d) — stopping", cycle, d.max_replan_cycles)
        update_state_field(state_file, "status", "done")
        update_state_field(state_file, "replan_limit_reached", True)
        from .merger import cleanup_all_worktrees
        cleanup_all_worktrees(state_file)
        _send_terminal_notifications(state_file, "replan_limit", event_bus)
        _generate_report_safe(state_file)
        _generate_review_findings_summary_safe(state_file)
        _persist_run_learnings(state_file)
        return True

    replan_attempt = state.extras.get("replan_attempt", 0)
    if replan_attempt == 0:
        cycle += 1
        update_state_field(state_file, "replan_cycle", cycle)

    logger.info("Auto-replanning (cycle %d/%d)...", cycle, d.max_replan_cycles)

    try:
        replan_result = _auto_replan_cycle(state_file, d, cycle, event_bus)
    except Exception:
        logger.error("Replan cycle %d failed with exception", cycle, exc_info=True)
        replan_result = "error"

    if replan_result == "dispatched":
        update_state_field(state_file, "replan_attempt", 0)
        logger.info("Replan cycle %d: new changes dispatched", cycle)
        return False  # continue monitoring

    if replan_result == "no_new_work":
        update_state_field(state_file, "replan_attempt", 0)
        update_state_field(state_file, "status", "done")
        from .merger import cleanup_all_worktrees
        cleanup_all_worktrees(state_file)
        _send_terminal_notifications(state_file, "done", event_bus)
        _generate_report_safe(state_file)
        _generate_review_findings_summary_safe(state_file)
        _persist_run_learnings(state_file)
        return True

    # Replan failed — retry with limit
    replan_attempt += 1
    update_state_field(state_file, "replan_attempt", replan_attempt)

    if replan_attempt >= DEFAULT_MAX_REPLAN_RETRIES:
        logger.error("Replan failed %d consecutive times — giving up", replan_attempt)
        update_state_field(state_file, "status", "done")
        update_state_field(state_file, "replan_exhausted", True)
        update_state_field(state_file, "replan_attempt", 0)
        _send_terminal_notifications(state_file, "replan_exhausted", event_bus)
        _generate_report_safe(state_file)
        _generate_review_findings_summary_safe(state_file)
        _persist_run_learnings(state_file)
        return True

    logger.warning("Replan failed (cycle %d, attempt %d) — will retry", cycle, replan_attempt)
    time.sleep(30)
    return False  # continue monitoring


def _get_issue_owned_changes() -> set[str]:
    """Return change names actively owned by the issue pipeline.

    Reads .set/issues/registry.json. Changes with active issues
    (investigating/fixing/awaiting_approval) should not be retried
    or redispatched by the orchestrator — the issue pipeline handles them.
    """
    registry_path = os.path.join(os.getcwd(), ".set", "issues", "registry.json")
    if not os.path.isfile(registry_path):
        return set()
    try:
        with open(registry_path) as f:
            data = json.load(f)
        active_states = {"investigating", "fixing", "awaiting_approval", "diagnosed"}
        owned = set()
        for issue in data.get("issues", []):
            if issue.get("state") in active_states and issue.get("affected_change"):
                owned.add(issue["affected_change"])
        return owned
    except (json.JSONDecodeError, OSError):
        return set()


def _resolve_issues_for_change(change_name: str) -> int:
    """Auto-resolve active issues for a change that completed successfully.

    When an agent finishes (status=done), any active issues blocking the
    merge queue for that change are stale — the agent already fixed whatever
    the issue was about. Resolve them so the merger can proceed immediately.

    Returns the number of issues resolved.
    """
    registry_path = os.path.join(os.getcwd(), ".set", "issues", "registry.json")
    if not os.path.isfile(registry_path):
        return 0
    try:
        with open(registry_path) as f:
            data = json.load(f)
        active_states = {"open", "investigating", "diagnosed", "fixing", "awaiting_approval"}
        resolved_count = 0
        now_iso = datetime.now(timezone.utc).isoformat()
        for issue in data.get("issues", []):
            if issue.get("affected_change") == change_name and issue.get("state") in active_states:
                issue["state"] = "resolved"
                issue["resolved_at"] = now_iso
                issue["updated_at"] = now_iso
                resolved_count += 1
        if resolved_count > 0:
            with open(registry_path, "w") as f:
                json.dump(data, f, indent=4)
            logger.info(
                "Auto-resolved %d active issue(s) for completed change %s",
                resolved_count, change_name,
            )
        return resolved_count
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to auto-resolve issues for %s", change_name, exc_info=True)
        return 0


def _get_issue_owned_changes_with_ts() -> dict[str, int]:
    """Return change names actively owned by the issue pipeline with ownership start time.

    Returns dict of {change_name: ownership_start_epoch}.
    Uses issue detected_at as ownership start timestamp.
    """
    registry_path = os.path.join(os.getcwd(), ".set", "issues", "registry.json")
    if not os.path.isfile(registry_path):
        return {}
    try:
        with open(registry_path) as f:
            data = json.load(f)
        active_states = {"investigating", "fixing", "awaiting_approval", "diagnosed"}
        owned: dict[str, int] = {}
        for issue in data.get("issues", []):
            if issue.get("state") in active_states and issue.get("affected_change"):
                # Parse ISO timestamp to epoch
                detected = issue.get("detected_at", "")
                try:
                    dt = datetime.fromisoformat(detected)
                    epoch = int(dt.timestamp())
                except (ValueError, TypeError):
                    epoch = 0
                change_name = issue["affected_change"]
                # Keep earliest ownership start if multiple issues
                if change_name not in owned or epoch < owned[change_name]:
                    owned[change_name] = epoch
        return owned
    except (json.JSONDecodeError, OSError):
        return {}


def _all_coverage_merged() -> bool:
    """Check if all requirements in coverage.json have status 'merged'.

    Returns True if there are no uncovered requirements — meaning replan is unnecessary.
    Returns True (skip replan) if no coverage data exists (can't determine gaps).
    """
    digest_dir = os.path.join(os.getcwd(), "set", "orchestration", "digest")
    reqs_path = os.path.join(digest_dir, "requirements.json")
    cov_path = os.path.join(digest_dir, "coverage.json")

    if not os.path.isfile(reqs_path):
        return True  # No requirements data — nothing to gap-check

    try:
        with open(reqs_path) as f:
            reqs_data = json.load(f)
        all_reqs = [r for r in reqs_data.get("requirements", []) if r.get("status") != "removed"]
        if not all_reqs:
            return True  # No active requirements
    except (json.JSONDecodeError, OSError):
        return True

    coverage: dict = {}
    if os.path.isfile(cov_path):
        try:
            with open(cov_path) as f:
                cov_data = json.load(f)
            coverage = cov_data.get("coverage", {})
        except (json.JSONDecodeError, OSError):
            pass

    uncovered = [r["id"] for r in all_reqs if r["id"] not in coverage or coverage[r["id"]].get("status") != "merged"]
    if uncovered:
        logger.info("Coverage gaps: %d/%d requirements uncovered: %s", len(uncovered), len(all_reqs), uncovered[:5])
        return False

    logger.info("All %d requirements covered — no replan needed", len(all_reqs))
    return True


def _detect_replan_trigger(state_file: str) -> str:
    """Detect what triggered the replan: domain_failure, e2e_failure, spec_change, coverage_gap.

    Returns one of: "domain_failure", "e2e_failure", "spec_change", "coverage_gap", "batch_complete".
    """
    try:
        state = load_state(state_file)
    except Exception:
        return "batch_complete"

    # E2E failure takes priority
    if state.extras.get("phase_e2e_failure_context"):
        return "e2e_failure"

    # Check for failed/stalled changes
    has_failed = any(c.status in ("failed", "stalled") for c in state.changes)
    if has_failed:
        return "domain_failure"

    # Check for coverage gaps
    coverage_path = os.path.join(os.getcwd(), "set", "orchestration", "digest", "coverage.json")
    if os.path.isfile(coverage_path):
        try:
            with open(coverage_path) as f:
                cov_data = json.load(f)
            uncovered = cov_data.get("uncovered", [])
            if uncovered:
                return "coverage_gap"
        except (json.JSONDecodeError, OSError):
            pass

    return "batch_complete"


def _get_domains_needing_replan(state_file: str, domain_data: dict, trigger: str) -> list[str]:
    """Get list of domain names that need Phase 2 re-run."""
    try:
        state = load_state(state_file)
    except Exception:
        return [d["name"] for d in domain_data["domains"]]

    if trigger == "domain_failure":
        # Find domains of failed/stalled changes
        failed_changes = [c for c in state.changes if c.status in ("failed", "stalled")]
        # Map change names to domains via requirements
        failed_domains = set()
        plan_file = os.environ.get("PLAN_FILENAME", "orchestration-plan.json")
        if os.path.isfile(plan_file):
            try:
                with open(plan_file) as f:
                    plan = json.load(f)
                # Build change→domain map from requirements
                req_to_domain = {}
                for d in domain_data["domains"]:
                    for r in d["requirements"]:
                        req_to_domain[r["id"]] = d["name"]

                for fc in failed_changes:
                    # Find this change in plan and get its requirements
                    for pc in plan.get("changes", []):
                        if pc.get("name") == fc.name:
                            for req_id in pc.get("requirements", []):
                                domain = req_to_domain.get(req_id)
                                if domain:
                                    failed_domains.add(domain)
                            break
            except (json.JSONDecodeError, OSError):
                pass
        return list(failed_domains) if failed_domains else [domain_data["domains"][0]["name"]]

    if trigger == "coverage_gap":
        # Find domains with uncovered requirements
        coverage_path = os.path.join(os.getcwd(), "set", "orchestration", "digest", "coverage.json")
        gap_domains = set()
        try:
            with open(coverage_path) as f:
                cov_data = json.load(f)
            uncovered = cov_data.get("uncovered", [])
            # Map uncovered req IDs to domains
            for d in domain_data["domains"]:
                domain_req_ids = {r["id"] for r in d["requirements"]}
                if domain_req_ids & set(uncovered):
                    gap_domains.add(d["name"])
        except (json.JSONDecodeError, OSError):
            pass
        return list(gap_domains) if gap_domains else [domain_data["domains"][0]["name"]]

    return [d["name"] for d in domain_data["domains"]]


def _auto_replan_cycle(
    state_file: str, d: Directives, cycle: int, event_bus: Any
) -> str:
    """Execute one auto-replan cycle entirely in Python.

    Returns: "dispatched", "no_new_work", or "error".
    """
    from .planner import collect_replan_context, build_decomposition_context, validate_plan, enrich_plan_metadata
    from .subprocess_utils import run_claude_logged
    from .dispatcher import dispatch_ready_changes

    # 1. Archive completed changes to state-archive.jsonl
    _archive_completed_to_jsonl(state_file)

    # 2. Collect replan context
    replan_ctx = collect_replan_context(state_file)
    if not replan_ctx.get("completed_names"):
        logger.warning("Replan: no completed changes found — nothing to build on")
        return "no_new_work"

    # 3. Read plan metadata for input_mode/input_path
    plan_file = os.environ.get("PLAN_FILENAME", "orchestration-plan.json")
    if not os.path.isfile(plan_file):
        logger.error("Replan: plan file not found at %s", plan_file)
        return "error"

    with open(plan_file) as f:
        plan_data = json.load(f)

    input_mode = plan_data.get("input_mode", "spec")
    input_path = plan_data.get("input_path", "")

    # 4. Determine replan trigger type and use appropriate pipeline
    replan_trigger = _detect_replan_trigger(state_file)

    # 5. Domain-parallel selective replan (digest mode) or single-call (brief/spec)
    domains_file = os.path.join(os.path.dirname(plan_file), "orchestration-plan-domains.json")
    if input_mode == "digest" and os.path.isfile(domains_file):
        # ── Selective Domain-Parallel Replan ──
        from .planner import (
            _load_domain_data, _phase1_planning_brief,
            _decompose_single_domain, _phase2_parallel_decompose,
            _phase3_merge_plans, _save_domain_plans,
        )

        logger.info("Replan: using domain-parallel pipeline (trigger=%s)", replan_trigger)

        # Load saved domain plans
        with open(domains_file) as f:
            saved = json.load(f)
        saved_brief = saved.get("brief", {})
        saved_domain_plans = saved.get("domain_plans", {})

        digest_dir = os.path.join(os.getcwd(), "set", "orchestration", "digest")
        domain_data = _load_domain_data(digest_dir)
        model = d.default_model or "opus"

        if replan_trigger == "spec_change":
            # Full re-decompose
            logger.info("Replan: full re-decompose (spec changed)")
            saved_brief = _phase1_planning_brief(domain_data, model=model)
            saved_domain_plans = _phase2_parallel_decompose(domain_data, saved_brief, model=model)
        elif replan_trigger == "e2e_failure":
            # Phase 3 only — re-merge with failure context
            logger.info("Replan: Phase 3 only (E2E failure)")
        elif replan_trigger in ("domain_failure", "coverage_gap"):
            # Re-run failed/gap domains only
            failed_domains = _get_domains_needing_replan(state_file, domain_data, replan_trigger)
            logger.info("Replan: re-decomposing domains: %s", failed_domains)
            for dname in failed_domains:
                domain = next((dom for dom in domain_data["domains"] if dom["name"] == dname), None)
                if domain:
                    saved_domain_plans[dname] = _decompose_single_domain(
                        domain, json.dumps(saved_brief), domain_data["conventions"], model=model,
                    )
        else:
            # "batch_complete" — check coverage before full re-decompose
            if _all_coverage_merged():
                logger.info("Replan: batch_complete but coverage is 100%% — no new work needed")
                return "no_new_work"
            # Coverage gaps exist — treat as coverage_gap (selective, not full re-decompose)
            logger.info("Replan: batch_complete with coverage gaps — using selective re-decompose")
            failed_domains = _get_domains_needing_replan(state_file, domain_data, "coverage_gap")
            if not failed_domains:
                return "no_new_work"
            for dname in failed_domains:
                domain = next((dom for dom in domain_data["domains"] if dom["name"] == dname), None)
                if domain:
                    saved_domain_plans[dname] = _decompose_single_domain(
                        domain, json.dumps(saved_brief), domain_data["conventions"], model=model,
                    )

        _save_domain_plans(saved_brief, saved_domain_plans)

        plan_json = _phase3_merge_plans(
            saved_domain_plans, saved_brief, domain_data,
            replan_ctx=replan_ctx, model=model,
        )
    else:
        # ── Single-call replan (brief/spec mode) ──
        context = build_decomposition_context(
            input_mode, input_path,
            replan_ctx=replan_ctx,
        )

        from .templates import render_planning_prompt
        prompt = render_planning_prompt(**context)

        claude_result = run_claude_logged(prompt, purpose="replan", timeout=1800, model=d.default_model or "opus")
        if claude_result.exit_code != 0:
            logger.error("Replan: Claude invocation failed (exit %d)", claude_result.exit_code)
            return "error"

        response_text = claude_result.stdout.strip()

        plan_json = None
        try:
            plan_json = json.loads(response_text)
        except json.JSONDecodeError:
            import re
            match = re.search(r'```(?:json)?\s*\n(.*?)\n```', response_text, re.DOTALL)
            if match:
                try:
                    plan_json = json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass
            if plan_json is None:
                first = response_text.find("{")
                last = response_text.rfind("}")
                if first >= 0 and last > first:
                    try:
                        plan_json = json.loads(response_text[first:last + 1])
                    except json.JSONDecodeError:
                        pass

    if not plan_json or "changes" not in plan_json:
        logger.error("Replan: could not parse plan JSON from Claude response")
        return "error"

    new_changes = plan_json.get("changes", [])
    if not new_changes:
        logger.info("Replan: Claude returned empty changes list")
        return "no_new_work"

    # 7. Novelty check — skip if all changes duplicate previously failed ones
    state = load_state(state_file)
    failed_names = {c.name for c in state.changes if c.status == "failed"}
    new_names = {c.get("name", "") for c in new_changes}
    if new_names and new_names.issubset(failed_names):
        logger.info("Replan: all %d new changes are duplicates of failed ones — no new work", len(new_names))
        return "no_new_work"

    # 8. Write updated plan
    plan_data["changes"] = new_changes
    plan_data["replan_cycle"] = cycle
    with open(plan_file, "w") as f:
        json.dump(plan_data, f, indent=2)

    # 9. Add new changes to existing state
    _append_changes_to_state(state_file, new_changes)

    dispatch_ready_changes(
        state_file, d.max_parallel,
        default_model=d.default_model,
        model_routing=d.model_routing,
        team_mode=d.team_mode,
        context_pruning=d.context_pruning,
        event_bus=event_bus,
        design_snapshot_dir=os.getcwd(),
    )

    if event_bus:
        event_bus.emit("REPLAN_DISPATCHED", data={"cycle": cycle, "changes": len(new_changes)})

    return "dispatched"


def _append_changes_to_state(state_file: str, new_changes: list[dict]) -> None:
    """Append new plan changes to existing orchestration state."""
    from .state import Change, locked_state

    with locked_state(state_file) as state:
        existing_names = {c.name for c in state.changes}
        for c in new_changes:
            if c.get("name") in existing_names:
                continue
            change = Change(
                name=c["name"],
                scope=c.get("scope", ""),
                complexity=c.get("complexity", "M"),
                change_type=c.get("change_type", "feature"),
                depends_on=c.get("depends_on", []),
                roadmap_item=c.get("roadmap_item", ""),
                model=c.get("model", None),
                phase=c.get("phase", 1),
                gate_hints=c.get("gate_hints") or None,
            )
            state.changes.append(change)
        logger.info("Appended %d new changes to state", len(new_changes))


def _archive_completed_to_jsonl(state_file: str) -> None:
    """Archive completed changes to state-archive.jsonl before replan."""
    state = load_state(state_file)
    archive_path = os.path.join(os.path.dirname(state_file), "state-archive.jsonl")

    completed = [
        c for c in state.changes
        if c.status in ("merged", "done", "failed", "merge-blocked", "skipped", "integration-failed")
    ]
    if not completed:
        return

    try:
        with open(archive_path, "a") as f:
            for c in completed:
                entry = {
                    "name": c.name,
                    "status": c.status,
                    "tokens_used": c.tokens_used,
                    "scope": c.scope,
                    "archived_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                f.write(json.dumps(entry) + "\n")
        logger.info("Archived %d completed changes to %s", len(completed), archive_path)
    except OSError:
        logger.warning("Failed to archive completed changes")


# ─── Utility Helpers ───────────────────────────────────────────────

def _any_loop_active(state_file: str) -> bool:
    """Check if any change has an active loop (running status)."""
    state = load_state(state_file)
    return any(c.status == "running" for c in state.changes)


def _count_by_status(state_file: str, status: str) -> int:
    """Count changes with a specific status."""
    state = load_state(state_file)
    return sum(1 for c in state.changes if c.status == status)


def _dispatch_ready_safe(state_file: str, d: Directives, event_bus: Any) -> None:
    """Dispatch ready changes (exception-safe wrapper)."""
    try:
        from .dispatcher import dispatch_ready_changes
        dispatch_ready_changes(
            state_file, d.max_parallel,
            default_model=d.default_model,
            model_routing=d.model_routing,
            team_mode=d.team_mode,
            context_pruning=d.context_pruning,
            event_bus=event_bus,
            design_snapshot_dir=os.getcwd(),
        )
    except Exception:
        logger.warning("Dispatch failed", exc_info=True)


def _recover_dep_blocked_safe(state_file: str, event_bus: Any) -> None:
    """Recover dep-blocked changes whose dependencies are now in terminal status."""
    try:
        state = load_state(state_file)
        terminal = {"merged", "done", "skip_merged", "completed", "skipped"}
        for change in state.changes:
            if change.status != "dep-blocked":
                continue
            deps = change.depends_on or []
            if not deps:
                # No deps but dep-blocked — recover
                update_change_field(state_file, change.name, "status", "done", event_bus=event_bus)
                logger.info("Recovered dep-blocked %s — no dependencies listed", change.name)
                continue
            all_met = True
            for dep_name in deps:
                dep = next((c for c in state.changes if c.name == dep_name), None)
                if not dep or dep.status not in terminal:
                    all_met = False
                    break
            if all_met:
                update_change_field(state_file, change.name, "status", "done", event_bus=event_bus)
                logger.info("Recovered dep-blocked %s — all dependencies now merged", change.name)
    except Exception:
        logger.warning("dep-blocked recovery failed", exc_info=True)


def _recover_merge_blocked_safe(state_file: str, event_bus: Any) -> None:
    """Recover merge-blocked changes whose blocking issues are resolved."""
    try:
        state = load_state(state_file)
        blocked = [c for c in state.changes if c.status == "merge-blocked"]
        if not blocked:
            return
        # Read issue registry
        registry_path = os.path.join(os.getcwd(), ".set", "issues", "registry.json")
        issues = []
        if os.path.isfile(registry_path):
            try:
                with open(registry_path) as f:
                    issues = json.load(f).get("issues", [])
            except (json.JSONDecodeError, OSError):
                pass
        active_issue_states = {"open", "investigating", "diagnosed", "fixing", "awaiting_approval"}
        for change in blocked:
            # Find issues referencing this change
            change_issues = [
                i for i in issues
                if i.get("affected_change") == change.name
            ]
            has_active = any(i.get("state") in active_issue_states for i in change_issues)
            if not has_active:
                # No active blockers — recover
                update_change_field(state_file, change.name, "status", "done", event_bus=event_bus)
                logger.info(
                    "Recovered merge-blocked %s — %s",
                    change.name,
                    "blocking issues resolved" if change_issues else "no blocking issues found",
                )
    except Exception:
        logger.warning("merge-blocked recovery failed", exc_info=True)


def _retry_merge_queue_safe(state_file: str, event_bus: Any) -> None:
    """Retry merge queue (exception-safe)."""
    try:
        from .merger import retry_merge_queue
        retry_merge_queue(state_file, event_bus=event_bus)
    except Exception:
        logger.warning("Merge queue retry failed", exc_info=True)


def _drain_merge_then_dispatch(
    state_file: str, d: "Directives", event_bus: Any
) -> int:
    """Drain the merge queue completely, then dispatch ready changes.

    Serializes merge and dispatch: archive commits land on main BEFORE
    new worktrees are created, eliminating the archive race (Bug #38)
    where new worktrees miss openspec/changes/ deletions.

    Returns count of changes merged.
    """
    merged = 0
    try:
        from .merger import retry_merge_queue
        merged = retry_merge_queue(state_file, event_bus=event_bus)
        if merged > 0:
            logger.info("Drain-then-dispatch: merged %d change(s) before dispatch", merged)
    except Exception:
        logger.warning("Drain-then-dispatch: merge failed", exc_info=True)

    # Dispatch after merge — worktrees created with archive commits present
    _dispatch_ready_safe(state_file, d, event_bus)
    return merged


def _resume_stalled_safe(state_file: str, event_bus: Any) -> None:
    """Resume stalled changes (exception-safe)."""
    try:
        from .dispatcher import resume_stalled_changes
        resume_stalled_changes(state_file, event_bus=event_bus)
    except Exception:
        logger.warning("Resume stalled failed", exc_info=True)


def _retry_failed_builds_safe(state_file: str, d: Directives, event_bus: Any) -> None:
    """Retry failed builds (exception-safe)."""
    try:
        from .dispatcher import retry_failed_builds
        retry_failed_builds(state_file, max_retries=d.max_verify_retries, event_bus=event_bus)
    except Exception:
        logger.warning("Retry failed builds failed", exc_info=True)


def _check_token_hard_limit(state_file: str, d: Directives, event_bus: Any = None) -> None:
    """Check token hard limit and trigger checkpoint if exceeded."""
    # Source: monitor.sh L354-377
    state = load_state(state_file)
    total_tokens = sum(c.tokens_used for c in state.changes)
    prev_tokens = state.extras.get("prev_total_tokens", 0)
    cumulative = total_tokens + prev_tokens

    if cumulative <= d.token_hard_limit:
        return

    already_triggered = state.extras.get("token_hard_limit_triggered", False)
    if already_triggered:
        return

    update_state_field(state_file, "token_hard_limit_triggered", True)
    logger.warning(
        "Token hard limit reached: %dM / %dM tokens",
        cumulative // 1_000_000, d.token_hard_limit // 1_000_000,
    )
    _trigger_checkpoint_safe(state_file, "token_hard_limit", event_bus)
    update_state_field(state_file, "token_hard_limit_triggered", False)


def _self_watchdog(
    state_file: str, d: Directives,
    last_progress_ts: int, escalation: int, event_bus: Any,
) -> None:
    """Self-watchdog: detect all-idle stall."""
    # Source: monitor.sh L379-410
    now = int(time.time())
    idle_duration = now - last_progress_ts

    if idle_duration <= d.monitor_idle_timeout:
        return

    if escalation == 0:
        # First: attempt recovery — drain merge queue then dispatch
        logger.warning("Monitor self-watchdog: no progress for %ds — attempting recovery", idle_duration)
        _drain_merge_then_dispatch(state_file, d, event_bus)

        # Check orphaned "done" changes
        state = load_state(state_file)
        for change in state.changes:
            if change.status != "done":
                continue
            if change.name not in state.merge_queue:
                logger.warning("Monitor self-watchdog: orphaned 'done' %s — adding to merge queue", change.name)
                with locked_state(state_file) as st:
                    if change.name not in st.merge_queue:
                        st.merge_queue.append(change.name)
    else:
        # Persistent idle: escalate
        logger.error(
            "Monitor self-watchdog: persistent idle (%ds, escalation #%d)",
            idle_duration, escalation,
        )
        if event_bus:
            event_bus.emit(
                "MONITOR_STALL",
                data={"idle_secs": idle_duration, "escalation": escalation},
            )


def _check_phase_completion(
    state_file: str, d: Directives, event_bus: Any
) -> None:
    """Check phase completion, run optional milestone, and advance phase.

    Phase advancement ALWAYS happens when all changes in the current phase
    are terminal. Milestone checkpoints only run if milestones_enabled.
    Bug #17 fix: previously phase advancement was gated behind
    milestones_enabled, so phases never advanced when milestones were off.
    """
    state = load_state(state_file)
    current_phase = state.extras.get("current_phase", 999)
    if current_phase >= 999:
        return

    # Check if all changes in current phase are terminal
    # Pending changes with failed deps are effectively terminal (will never run)
    from .state import deps_failed
    phase_changes = [c for c in state.changes if c.phase == current_phase]
    terminal_statuses = {"merged", "done", "skipped", "failed", "merge-blocked", "integration-failed", "awaiting_confirmation"}
    all_terminal = all(
        c.status in terminal_statuses or (c.status == "pending" and deps_failed(state, c.name))
        for c in phase_changes
    )

    if not all_terminal or not phase_changes:
        return

    logger.info("Phase %d complete — advancing", current_phase)

    # Optional milestone checkpoint
    if d.milestones_enabled:
        from .milestone import run_milestone_checkpoint
        run_milestone_checkpoint(
            current_phase,
            base_port=d.milestones_base_port,
            max_worktrees=d.milestones_max_worktrees,
            state_file=state_file,
            milestone_dev_server=d.milestones_dev_server,
            event_bus=event_bus,
        )

    # Advance phase (always)
    from .state import advance_phase
    with locked_state(state_file) as st:
        advance_phase(st, event_bus=event_bus)


def _send_terminal_notifications(
    state_file: str, reason: str, event_bus: Any = None,
) -> None:
    """Send desktop notification + summary email at terminal state."""
    try:
        from .notifications import send_notification, send_summary_email
        from .digest import final_coverage_check

        state = load_state(state_file)
        total = len(state.changes)
        merged = sum(1 for c in state.changes if c.status == "merged")

        # Regenerate spec-coverage-report.md with live statuses
        try:
            from .planner import generate_coverage_report
            import json as _json
            # Use absolute paths based on state_file location
            _project_dir = os.path.dirname(os.path.abspath(state_file))
            plan_path = os.path.join(_project_dir, "orchestration-plan.json")
            plan_data = {}
            if os.path.isfile(plan_path):
                plan_data = _json.loads(open(plan_path).read())
            try:
                from .paths import SetRuntime
                _rt = SetRuntime()
                _default_digest = _rt.digest_dir
                _default_coverage = _rt.spec_coverage_report
            except Exception:
                _default_digest = os.path.join(_project_dir, "set", "orchestration", "digest")
                _default_coverage = os.path.join(_project_dir, "set", "orchestration", "spec-coverage-report.md")
            digest_dir = state.extras.get("digest_dir", _default_digest)
            if not os.path.isabs(digest_dir):
                digest_dir = os.path.join(_project_dir, digest_dir)
            if not os.path.isdir(digest_dir):
                digest_dir = ""
            if not os.path.isabs(_default_coverage):
                _default_coverage = os.path.join(_project_dir, _default_coverage)
            generate_coverage_report(
                plan=plan_data,
                digest_dir=digest_dir,
                output_path=_default_coverage,
                state_file=state_file,
                plan_path=plan_path,
            )
        except Exception:
            logger.debug("Terminal coverage report regeneration failed (non-critical)", exc_info=True)

        title = f"Orchestration {reason}"
        body = f"{merged}/{total} changes merged"

        send_notification(title, body, urgency="normal", channels="desktop,email")
        coverage = final_coverage_check()
        send_summary_email(state_file, coverage_summary=coverage)
    except Exception:
        logger.debug("Terminal notification failed (non-critical)", exc_info=True)


def _periodic_memory_ops_safe(state_file: str) -> None:
    """Run periodic memory operations (exception-safe)."""
    try:
        from .orch_memory import orch_memory_stats, orch_gate_stats, orch_memory_audit

        orch_memory_stats()

        state = load_state(state_file)
        orch_gate_stats(state.to_dict() if hasattr(state, 'to_dict') else {"changes": []})

        orch_memory_audit()
    except Exception:
        logger.debug("Periodic memory ops failed (non-critical)", exc_info=True)


def _generate_report_safe(state_file: str) -> None:
    """Generate HTML report (exception-safe)."""
    try:
        from .reporter import generate_report
        generate_report(state_path=state_file)
    except Exception:
        pass


def _generate_review_findings_summary_safe(state_file: str) -> None:
    """Generate review findings summary from JSONL log (exception-safe)."""
    try:
        from .verifier import generate_review_findings_summary
        findings_dir = os.path.join(os.path.dirname(state_file), "set", "orchestration")
        findings_path = os.path.join(findings_dir, "review-findings.jsonl")
        summary_path = os.path.join(findings_dir, "review-findings-summary.md")
        result = generate_review_findings_summary(findings_path, summary_path)
        if result:
            logger.info("Review findings summary: %s", result)
    except Exception:
        pass


def _persist_run_learnings(state_file: str) -> None:
    """Persist gate stats and review patterns to memory at run end (exception-safe)."""
    try:
        from .orch_memory import orch_remember, orch_gate_stats
        from .state import load_state

        state = load_state(state_file)
        state_dict = state.to_dict() if hasattr(state, "to_dict") else {}

        # Gate stats summary
        gate_stats = orch_gate_stats(state_dict)
        if gate_stats and gate_stats.get("changes_with_gate", 0) > 0:
            summary = (
                f"Gate stats: {gate_stats['changes_with_gate']} changes, "
                f"total {gate_stats.get('total_gate_secs', 0)}s gate time "
                f"({gate_stats.get('gate_pct', 0)}% of run), "
                f"{gate_stats.get('total_retry_count', 0)} retries"
            )
            orch_remember(summary, mem_type="Context", tags="source:orchestrator,type:gate-stats")
            logger.info("Persisted gate stats to memory")

        # Recurring review patterns — try JSONL first, fall back to state review_output
        import re as _re
        pattern_counts: dict[str, set[str]] = {}

        findings_dir = os.path.join(os.path.dirname(state_file), "set", "orchestration")
        findings_path = os.path.join(findings_dir, "review-findings.jsonl")
        if os.path.isfile(findings_path):
            with open(findings_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    change = entry.get("change", "")
                    for issue in entry.get("issues", []):
                        norm = _re.sub(r"\[(?:CRITICAL|HIGH|MEDIUM)\]\s*", "", issue.get("summary", ""))[:80]
                        if norm:
                            pattern_counts.setdefault(norm, set()).add(change)

        # Fallback: extract from state review_output (always available)
        if not pattern_counts:
            changes_list = state_dict.get("changes", [])
            for c in changes_list:
                review_out = c.get("review_output", "")
                if not review_out:
                    continue
                change_name = c.get("name", "")
                for match in _re.finditer(r"\[(?:CRITICAL|HIGH)\]\s*(.+?)(?:\n|$)", review_out):
                    norm = match.group(1).strip()[:80]
                    if norm:
                        pattern_counts.setdefault(norm, set()).add(change_name)

        # Also cluster by keywords for fuzzy matching across variations
        from .review_clusters import REVIEW_PATTERN_CLUSTERS
        _CLUSTERS = REVIEW_PATTERN_CLUSTERS
        cluster_counts: dict[str, set[str]] = {}
        for norm, changes_set in pattern_counts.items():
            norm_lower = norm.lower()
            for cid, keywords in _CLUSTERS.items():
                if any(kw in norm_lower for kw in keywords):
                    cluster_counts.setdefault(cid, set()).update(changes_set)
                    break

        # Merge keyword clusters into pattern_counts
        for cid, changes_set in cluster_counts.items():
            if len(changes_set) >= 2:
                pattern_counts[f"[cluster:{cid}]"] = changes_set

        recurring = {k: v for k, v in pattern_counts.items() if len(v) >= 2}
        if recurring:
            lines = ["Recurring review patterns across changes:"]
            for pattern, changes in sorted(recurring.items(), key=lambda x: -len(x[1])):
                lines.append(f"- \"{pattern}\" in {len(changes)} changes: {', '.join(sorted(changes))}")
            orch_remember("\n".join(lines), mem_type="Learning", tags="source:orchestrator,type:review-patterns")
            logger.info("Persisted %d recurring review patterns to memory", len(recurring))

    except Exception:
        logger.debug("Failed to persist run learnings", exc_info=True)


def _clear_checkpoint_state(state_file: str) -> None:
    """Clear checkpoint-specific transient state on restart.

    Removes checkpoint_reason, checkpoint_started_at from extras and
    resets changes_since_checkpoint to 0. These fields are meaningful
    only within a single orchestrator execution.
    """
    with locked_state(state_file) as state:
        changed = False
        if "checkpoint_reason" in state.extras:
            del state.extras["checkpoint_reason"]
            changed = True
        if "checkpoint_started_at" in state.extras:
            del state.extras["checkpoint_started_at"]
            changed = True
        if state.changes_since_checkpoint != 0:
            state.changes_since_checkpoint = 0
            changed = True
        if changed:
            logger.info("Cleared checkpoint transient state on restart")


def _checkpoint_approved(state: OrchestratorState) -> bool:
    """Check if the latest checkpoint has been approved via API.

    Checks state.checkpoints[-1].get("approved", False), handling both
    the checkpoints list on the dataclass and a fallback in extras.
    Returns False if no checkpoints exist.
    """
    # Primary: check state.checkpoints list
    checkpoints = state.checkpoints
    if not checkpoints:
        # Fallback: check extras for legacy storage
        checkpoints = state.extras.get("checkpoints", [])
    if not checkpoints:
        return False
    latest = checkpoints[-1]
    if isinstance(latest, dict):
        return bool(latest.get("approved", False))
    return False


def trigger_checkpoint(state_file: str, reason: str, event_bus: Any = None) -> None:
    """Set state to checkpoint, log reason, emit CHECKPOINT event.

    Args:
        state_file: Path to state file.
        reason: Reason for checkpoint (e.g., "periodic", "token_hard_limit").
        event_bus: Optional EventBus for CHECKPOINT event emission.
    """
    update_state_field(state_file, "status", "checkpoint")
    update_state_field(state_file, "checkpoint_reason", reason)
    update_state_field(state_file, "changes_since_checkpoint", 0)
    update_state_field(state_file, "checkpoint_started_at", int(time.time()))
    # Append checkpoint record to state.checkpoints
    state = load_state(state_file)
    completed_count = sum(
        1 for c in state.changes if c.status in ("merged", "done", "skipped", "failed", "integration-failed")
    )
    checkpoint_record = {
        "reason": reason,
        "triggered_at": datetime.now().astimezone().isoformat(),
        "changes_completed": completed_count,
        "approved": False,
    }
    with locked_state(state_file) as st:
        st.checkpoints.append(checkpoint_record)
    logger.info("Checkpoint triggered: %s", reason)
    if event_bus:
        event_bus.emit("CHECKPOINT", data={"reason": reason})


def _trigger_checkpoint_safe(state_file: str, reason: str, event_bus: Any = None) -> None:
    """Trigger a checkpoint (exception-safe)."""
    try:
        trigger_checkpoint(state_file, reason, event_bus)
    except Exception:
        pass


# ─── JSON parsing helpers ──────────────────────────────────────────

def _int(d: dict, key: str, default: int) -> int:
    v = d.get(key, default)
    if v is None or v == "":
        return default
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def _str(d: dict, key: str, default: str) -> str:
    v = d.get(key, default)
    if v is None:
        return default
    return str(v)


def _bool(d: dict, key: str, default: bool) -> bool:
    v = d.get(key, default)
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() in ("true", "1", "yes")
    return default
