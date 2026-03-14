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
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from .root import WT_TOOLS_ROOT
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
DEFAULT_TIME_LIMIT = "5h"
DEFAULT_TOKEN_HARD_LIMIT = 50_000_000
DEFAULT_MONITOR_IDLE_TIMEOUT = 600
DEFAULT_MAX_REPLAN_RETRIES = 3
MAX_REPLAN_CYCLES = 5


# ─── Directives ────────────────────────────────────────────────────

@dataclass
class Directives:
    """Parsed orchestration directives from JSON input.

    Mirrors the ~40 variables parsed from JSON in monitor.sh L5-106.
    """

    max_parallel: int = 3
    checkpoint_every: int = 0
    test_command: str = ""
    merge_policy: str = "eager"
    token_budget: int = 0
    auto_replan: bool = False
    max_replan_cycles: int = MAX_REPLAN_CYCLES
    test_timeout: int = 300
    max_verify_retries: int = 1
    review_before_merge: bool = False
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


# ─── Monitor Loop ──────────────────────────────────────────────────

# Source: monitor.sh monitor_loop() L5-586
def monitor_loop(
    directives_json: str,
    state_file: str,
    *,
    poll_interval: int = DEFAULT_POLL_INTERVAL,
    event_bus: Any = None,
) -> None:
    """Run the main orchestration monitoring loop.

    This is the Python equivalent of monitor.sh monitor_loop().
    Parses directives, then loops: poll → dispatch → merge → replan → watchdog.
    """
    # Parse directives
    if os.path.isfile(directives_json):
        with open(directives_json) as f:
            raw = json.load(f)
    else:
        raw = json.loads(directives_json)

    d = parse_directives(raw)

    # Persist timing info
    start_epoch = int(time.time())
    update_state_field(state_file, "started_epoch", start_epoch)
    update_state_field(state_file, "time_limit_secs", d.time_limit_secs)

    # Restore active_seconds from state (cumulative across restarts)
    state = load_state(state_file)
    active_seconds = state.extras.get("active_seconds", 0)
    token_wait = False
    replan_retry_count = 0

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
            _generate_report_safe(state_file)
            break

        # Check external stop
        state = load_state(state_file)
        if state.status in ("stopped", "done"):
            _generate_report_safe(state_file)
            break
        if state.status in ("paused", "checkpoint"):
            continue

        # Poll active changes (running + verifying)
        poll_e2e_cmd = d.e2e_command if d.e2e_mode != "phase_end" else ""
        _poll_active_changes(state_file, d, poll_e2e_cmd, event_bus)

        # Safety net: check suspended changes
        _poll_suspended_changes(state_file, d, poll_e2e_cmd, event_bus)

        # Token budget enforcement
        if d.token_budget > 0:
            total_tokens = sum(c.tokens_used for c in load_state(state_file).changes)
            if total_tokens > d.token_budget:
                if not token_wait:
                    logger.warning("Token budget exceeded (%d > %d) — waiting", total_tokens, d.token_budget)
                    token_wait = True
                _retry_merge_queue_safe(state_file, event_bus)
                continue
            elif token_wait:
                logger.info("Token budget available — resuming dispatch")
                token_wait = False

        # Verify-failed recovery
        _recover_verify_failed(state_file, d, event_bus)

        # Cascade failed deps
        from .state import cascade_failed_deps
        with locked_state(state_file) as st:
            cascade_failed_deps(st, event_bus=event_bus)

        # Dispatch ready changes
        pre_running = _count_by_status(state_file, "running")
        _dispatch_ready_safe(state_file, d, event_bus)
        post_running = _count_by_status(state_file, "running")
        if post_running > pre_running:
            last_progress_ts = int(time.time())

        # Phase milestone check
        if d.milestones_enabled:
            _check_phase_milestone(state_file, d, event_bus)

        # Retry merge queue
        pre_merged = _count_by_status(state_file, "merged")
        _retry_merge_queue_safe(state_file, event_bus)
        post_merged = _count_by_status(state_file, "merged")
        if post_merged > pre_merged:
            last_progress_ts = int(time.time())

        # Resume stalled changes
        _resume_stalled_safe(state_file, event_bus)

        # Retry failed builds
        _retry_failed_builds_safe(state_file, d, event_bus)

        # Token hard limit
        if d.token_hard_limit > 0:
            _check_token_hard_limit(state_file, d)

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

        # Checkpoint check
        if d.checkpoint_every > 0:
            state = load_state(state_file)
            if state.changes_since_checkpoint >= d.checkpoint_every:
                _trigger_checkpoint_safe(state_file, "periodic")
                continue

        # Completion detection
        if _check_completion(state_file, d, event_bus):
            break


# ─── Poll Helpers ──────────────────────────────────────────────────

def _poll_active_changes(
    state_file: str, d: Directives, poll_e2e_cmd: str, event_bus: Any
) -> None:
    """Poll all running + verifying changes."""
    from .verifier import poll_change

    state = load_state(state_file)
    for change in state.changes:
        if change.status not in ("running", "verifying"):
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
        if change.status not in ("paused", "waiting:budget", "budget_exceeded", "done"):
            continue

        wt_path = change.worktree_path or ""

        # For "done" changes: check merge queue
        if change.status == "done":
            if change.name not in state.merge_queue:
                logger.warning("Monitor: orphaned 'done' change %s — adding to merge queue", change.name)
                with locked_state(state_file) as st:
                    if change.name not in st.merge_queue:
                        st.merge_queue.append(change.name)
            continue

        # Check loop-state for suspended changes
        if not wt_path:
            continue
        loop_state_path = os.path.join(wt_path, ".claude", "loop-state.json")
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
                )
        except Exception:
            pass


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
            new_count = change.verify_retry_count + 1
            logger.info("Recovering verify-failed %s (retry %d/%d)", change.name, new_count, d.max_verify_retries)
            update_change_field(state_file, change.name, "verify_retry_count", new_count)

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
            logger.info("Verify-failed %s exhausted retries — marking failed", change.name)
            update_change_field(state_file, change.name, "status", "failed")


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

    truly_complete = sum(
        1 for c in state.changes
        if c.status in ("done", "merged", "skipped")
    )
    failed_count = sum(1 for c in state.changes if c.status == "failed")
    merge_blocked = sum(1 for c in state.changes if c.status == "merge-blocked")
    active_count = sum(
        1 for c in state.changes
        if c.status in ("running", "pending", "verifying", "stalled")
    )

    # Partial completion: no active changes, some failed/blocked
    if active_count == 0 and truly_complete < total:
        terminal = truly_complete + failed_count + merge_blocked
        if terminal >= total:
            logger.info(
                "%d succeeded, %d failed, %d merge-blocked — all resolved",
                truly_complete, failed_count, merge_blocked,
            )

    all_resolved = truly_complete + failed_count + merge_blocked
    if truly_complete < total and not (active_count == 0 and all_resolved >= total):
        return False

    logger.info("All %d changes complete", total)

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
        _generate_report_safe(state_file)
        return True

    # Phase-end E2E
    if d.e2e_mode == "phase_end" and d.e2e_command and truly_complete > 0:
        from .verifier import run_phase_end_e2e
        run_phase_end_e2e(d.e2e_command, state_file, e2e_timeout=d.e2e_timeout, event_bus=event_bus)

    # Auto-replan
    if d.auto_replan:
        return _handle_auto_replan(state_file, d, event_bus)

    # Non-replan completion
    update_state_field(state_file, "status", "done")
    from .merger import cleanup_all_worktrees
    cleanup_all_worktrees(state_file)
    run_command(["git", "tag", "-f", "orch/complete", "HEAD"], timeout=10)
    _generate_report_safe(state_file)
    return True


def _handle_auto_replan(
    state_file: str, d: Directives, event_bus: Any
) -> bool:
    """Handle auto-replan cycle. Returns True if loop should exit."""
    # Source: monitor.sh L473-566
    state = load_state(state_file)
    cycle = state.extras.get("replan_cycle", 0)

    if cycle >= d.max_replan_cycles:
        logger.info("Replan cycle limit reached (%d/%d) — stopping", cycle, d.max_replan_cycles)
        update_state_field(state_file, "status", "done")
        update_state_field(state_file, "replan_limit_reached", True)
        from .merger import cleanup_all_worktrees
        cleanup_all_worktrees(state_file)
        _generate_report_safe(state_file)
        return True

    replan_attempt = state.extras.get("replan_attempt", 0)
    if replan_attempt == 0:
        cycle += 1
        update_state_field(state_file, "replan_cycle", cycle)

    logger.info("Auto-replanning (cycle %d/%d)...", cycle, d.max_replan_cycles)

    # Delegate to bash auto_replan_cycle (not yet migrated)
    replan_result = run_command(
        ["bash", "-c", f'source {WT_TOOLS_ROOT}/lib/orchestration/planner.sh && auto_replan_cycle "{{}}" {cycle}'],
        timeout=600,
    )

    if replan_result.exit_code == 0:
        # New plan dispatched
        update_state_field(state_file, "replan_attempt", 0)
        logger.info("Replan cycle %d: new changes dispatched", cycle)
        return False  # continue monitoring

    if replan_result.exit_code == 1:
        # No new work — genuinely done
        update_state_field(state_file, "replan_attempt", 0)
        update_state_field(state_file, "status", "done")
        from .merger import cleanup_all_worktrees
        cleanup_all_worktrees(state_file)
        _generate_report_safe(state_file)
        return True

    # Replan failed — retry with limit
    replan_attempt += 1
    update_state_field(state_file, "replan_attempt", replan_attempt)

    if replan_attempt >= DEFAULT_MAX_REPLAN_RETRIES:
        logger.error("Replan failed %d consecutive times — giving up", replan_attempt)
        update_state_field(state_file, "status", "done")
        update_state_field(state_file, "replan_exhausted", True)
        update_state_field(state_file, "replan_attempt", 0)
        _generate_report_safe(state_file)
        return True

    logger.warning("Replan failed (cycle %d, attempt %d) — will retry", cycle, replan_attempt)
    time.sleep(30)
    return False  # continue monitoring


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
        )
    except Exception:
        logger.warning("Dispatch failed", exc_info=True)


def _retry_merge_queue_safe(state_file: str, event_bus: Any) -> None:
    """Retry merge queue (exception-safe)."""
    try:
        from .merger import retry_merge_queue
        retry_merge_queue(state_file, event_bus=event_bus)
    except Exception:
        logger.warning("Merge queue retry failed", exc_info=True)


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


def _check_token_hard_limit(state_file: str, d: Directives) -> None:
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
    _trigger_checkpoint_safe(state_file, "token_hard_limit")
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
        # First: attempt recovery
        logger.warning("Monitor self-watchdog: no progress for %ds — attempting recovery", idle_duration)
        _retry_merge_queue_safe(state_file, event_bus)

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


def _check_phase_milestone(
    state_file: str, d: Directives, event_bus: Any
) -> None:
    """Check phase completion and run milestone checkpoint."""
    # Source: monitor.sh L322-337
    state = load_state(state_file)
    current_phase = state.extras.get("current_phase", 999)
    if current_phase >= 999:
        return

    # Check if all changes in current phase are terminal
    phase_changes = [c for c in state.changes if c.phase == current_phase]
    terminal_statuses = {"merged", "done", "skipped", "failed", "merge-blocked"}
    all_terminal = all(c.status in terminal_statuses for c in phase_changes)

    if not all_terminal or not phase_changes:
        return

    logger.info("Phase %d complete — running milestone checkpoint", current_phase)
    from .milestone import run_milestone_checkpoint
    run_milestone_checkpoint(
        current_phase,
        base_port=d.milestones_base_port,
        max_worktrees=d.milestones_max_worktrees,
        state_file=state_file,
        milestone_dev_server=d.milestones_dev_server,
        event_bus=event_bus,
    )

    # Advance phase
    from .state import advance_phase
    with locked_state(state_file) as st:
        advance_phase(st, event_bus=event_bus)


def _generate_report_safe(state_file: str) -> None:
    """Generate HTML report (exception-safe)."""
    try:
        from .reporter import generate_report
        generate_report(state_path=state_file)
    except Exception:
        pass


def _trigger_checkpoint_safe(state_file: str, reason: str) -> None:
    """Trigger a checkpoint (exception-safe)."""
    try:
        update_state_field(state_file, "status", "checkpoint")
        logger.info("Checkpoint triggered: %s", reason)
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
