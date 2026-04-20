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
from pathlib import Path
from typing import Any, Optional

from .root import SET_TOOLS_ROOT
from .state import (
    OrchestratorState,
    StateCorruptionError,
    load_state,
    locked_state,
    update_change_field,
    update_state_field,
)
from .subprocess_utils import run_command
from .truncate import smart_truncate_structured

logger = logging.getLogger(__name__)

# ─── Constants (from bash globals) ──────────────────────────────────

DEFAULT_POLL_INTERVAL = 15
DEFAULT_TIME_LIMIT = 0  # 0 = no limit; set "5h" or similar in config to enable
DEFAULT_TOKEN_HARD_LIMIT = 50_000_000
DEFAULT_MONITOR_IDLE_TIMEOUT = 1800
DEFAULT_MAX_REPLAN_RETRIES = 3
MAX_REPLAN_CYCLES = 5
VERIFY_TIMEOUT = 600  # 10 min max for verify gate
DEFAULT_E2E_RETRY_LIMIT = 3  # max integration-e2e redispatches per change


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
    test_timeout: int = 600
    max_verify_retries: int = 4
    e2e_retry_limit: int = DEFAULT_E2E_RETRY_LIMIT
    integration_smoke_blocking: bool = True  # Smoke failures block the merge by default
    integration_smoke_timeout: int = 300  # Per-change smoke run timeout (sibling specs)
    llm_verdict_classifier_enabled: bool = True  # Second Sonnet pass classifies LLM gate outputs into structured verdicts (review/spec-verify/investigator)
    supervisor_mode: str = "python"  # "python" (set-supervisor daemon) | "claude" (legacy sentinel.md) | "off" (no supervision)
    review_before_merge: bool = True
    review_model: str = "sonnet"
    digest_model: str = "sonnet"
    investigation_model: str = "sonnet"
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
    e2e_timeout: int = 3600  # 1h ceiling — see verifier.DEFAULT_E2E_TIMEOUT
    e2e_mode: str = "per_change"
    e2e_coverage_threshold: float = 0.8
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
    # Part 7: dispatcher regenerates input.md between ralph iterations when
    # the project-level review-learnings file (see LineagePaths) is newer. Opt-out for
    # pathological cases where the refresh would add noise (e.g. mass
    # migrations that already carry their own learnings).
    refresh_input_on_learnings_update: bool = True

    # Hook scripts
    hook_pre_dispatch: str = ""
    hook_post_verify: str = ""
    hook_pre_merge: str = ""
    hook_post_merge: str = ""
    hook_on_fail: str = ""

    # fix-replan-stuck-gate-and-decomposer: circuit breakers + retry policy.
    # After `max_stuck_loops` consecutive `loop_status=stuck` exits with an
    # identical `last_gate_fingerprint`, the change is hard-failed and
    # escalated to fix-iss. See retry-loop-completion spec.
    max_stuck_loops: int = 3
    # Per-change token-runaway breaker: cumulative input_token growth above
    # this delta without a gate-fingerprint change trips the breaker.
    per_change_token_runaway_threshold: int = 20_000_000
    # Cumulative verify-pipeline wall time budget per change (ms).
    max_retry_wall_time_ms: int = 1_800_000
    # Cap on consecutive cached verdicts before forcing a full gate run.
    max_consecutive_cache_uses: int = 2
    # Decomposer granularity budget.
    per_change_estimated_loc_threshold: int = 1500
    loc_schema_weight: int = 120
    loc_ambiguity_weight: int = 80
    # Replan divergent-plan reconciliation mode.
    divergent_plan_dir_cleanup: str = "enabled"


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
    d.integration_smoke_blocking = _bool(raw, "integration_smoke_blocking", d.integration_smoke_blocking)
    d.integration_smoke_timeout = _int(raw, "integration_smoke_timeout", d.integration_smoke_timeout)
    d.llm_verdict_classifier_enabled = _bool(raw, "llm_verdict_classifier_enabled", d.llm_verdict_classifier_enabled)
    d.supervisor_mode = _str(raw, "supervisor_mode", d.supervisor_mode)
    d.test_timeout = _int(raw, "test_timeout", d.test_timeout)
    d.max_verify_retries = _int(raw, "max_verify_retries", d.max_verify_retries)
    d.review_before_merge = _bool(raw, "review_before_merge", d.review_before_merge)
    d.review_model = _str(raw, "review_model", d.review_model)
    d.digest_model = _str(raw, "digest_model", d.digest_model)
    d.investigation_model = _str(raw, "investigation_model", d.investigation_model)
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
    d.e2e_coverage_threshold = float(raw.get("e2e_coverage_threshold", d.e2e_coverage_threshold))
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
    d.refresh_input_on_learnings_update = _bool(
        raw, "refresh_input_on_learnings_update", d.refresh_input_on_learnings_update,
    )

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

    # fix-replan-stuck-gate-and-decomposer directives
    d.max_stuck_loops = _int(raw, "max_stuck_loops", d.max_stuck_loops)
    d.per_change_token_runaway_threshold = _int(
        raw, "per_change_token_runaway_threshold", d.per_change_token_runaway_threshold,
    )
    d.max_retry_wall_time_ms = _int(raw, "max_retry_wall_time_ms", d.max_retry_wall_time_ms)
    d.max_consecutive_cache_uses = _int(
        raw, "max_consecutive_cache_uses", d.max_consecutive_cache_uses,
    )
    d.per_change_estimated_loc_threshold = _int(
        raw, "per_change_estimated_loc_threshold", d.per_change_estimated_loc_threshold,
    )
    d.loc_schema_weight = _int(raw, "loc_schema_weight", d.loc_schema_weight)
    d.loc_ambiguity_weight = _int(raw, "loc_ambiguity_weight", d.loc_ambiguity_weight)
    d.divergent_plan_dir_cleanup = _str(
        raw, "divergent_plan_dir_cleanup", d.divergent_plan_dir_cleanup,
    )

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


# ─── Orphan Cleanup ────────────────────────────────────────────────


def _cleanup_orphans(state_file: str) -> None:
    """Clean orphaned resources on orchestrator startup.

    Fixes three categories of detritus from previous crashes/restarts:
    1. Stale ralph_pid references (process dead but PID in state)
    2. Stuck current_step values (merged but step != done)
    3. Orphaned worktrees (exist on disk but not in state, or for merged changes)

    Conservative: never kills processes, skips dirty worktrees, skips active changes.
    """
    from .state import load_state, locked_state
    from .subprocess_utils import run_command

    state = load_state(state_file)
    pids_cleared = 0
    steps_fixed = 0
    worktrees_removed = 0
    queue_restored = 0

    # ── Phase 1: Fix stale PIDs and stuck steps ──
    with locked_state(state_file) as st:
        for change in st.changes:
            # Fix stale ralph_pid
            if change.ralph_pid:
                try:
                    os.kill(change.ralph_pid, 0)
                    # Process alive — leave it alone
                except OSError:
                    # Process dead — clear PID
                    old_pid = change.ralph_pid
                    change.ralph_pid = None
                    pids_cleared += 1

                    if change.status in ("merged", "done"):
                        change.current_step = "done"
                        logger.info("Cleared stale PID %d for %s (merged, step→done)", old_pid, change.name)
                    elif change.status == "running":
                        change.status = "stalled"
                        logger.info("Change %s stalled (PID %d dead)", change.name, old_pid)
                    else:
                        logger.info("Cleared stale PID %d for %s (status=%s)", old_pid, change.name, change.status)

            # Fix stuck current_step
            if change.status in ("merged", "done") and change.current_step not in ("done", None):
                old_step = change.current_step
                change.current_step = "done"
                steps_fixed += 1
                logger.info("Fixed stuck step for %s: %s → done", change.name, old_step)

        # Phase 1b: recover orphaned "integrating" changes after supervisor
        # restart.
        #
        # status=integrating is written in exactly one place:
        # verifier.py _integrate_main_into_branch, which runs at the START of
        # the verify pipeline BEFORE gates execute. The merger never sets this
        # status. So a restart in this state means either:
        #   (a) gates already passed; the change is between verifier's
        #       status=done write and its merge_queue.append — safe to merge.
        #   (b) the verify pipeline was mid-gate (or a gate reported fail and
        #       the retry dispatch hadn't happened yet) — NOT safe to merge.
        #
        # Distinguishing: _verify_gates_already_passed inspects the persisted
        # gate-result fields. All blocking gates pass → (a); any None or fail
        # → (b).
        #
        # Case (b) is reset to status=running with ralph_pid=None so the next
        # _poll_active_changes cycle detects "dead agent + loop_status=done"
        # and routes back through handle_change_done → full gate pipeline.
        # Retry counters are intentionally not incremented: a supervisor
        # restart is an infrastructure event, not a gate failure.
        #
        # Conservative: only act when worktree still exists on disk. A
        # missing worktree is handled by _poll_active_changes (marks stalled).
        for change in st.changes:
            if change.status != "integrating":
                continue
            wt = change.worktree_path or ""
            if not wt or not os.path.isdir(wt):
                continue

            if _verify_gates_already_passed(change):
                if change.name not in st.merge_queue:
                    st.merge_queue.append(change.name)
                    queue_restored += 1
                    logger.warning(
                        "Restored orphaned integrating %s to merge queue "
                        "(all pre-merge gates passed, worktree=%s)",
                        change.name, wt,
                    )
            else:
                # Pipeline interrupted before all gates passed — re-run via
                # the dead-agent-with-loop-done path, no retry slot consumed.
                old_status = change.status
                old_pid = change.ralph_pid
                change.status = "running"
                change.ralph_pid = None
                logger.warning(
                    "Interrupted integrating %s (gates incomplete) — "
                    "reset %s→running, pid %s→None for pipeline re-run",
                    change.name, old_status, old_pid,
                )

    # ── Phase 2: Clean orphaned worktrees ──
    project_dir = os.path.dirname(os.path.abspath(state_file))
    project_name = os.path.basename(project_dir)

    # List git worktrees
    wt_result = run_command(
        ["git", "worktree", "list", "--porcelain"],
        timeout=10,
        cwd=project_dir,
    )
    if wt_result.exit_code != 0:
        logger.debug("git worktree list failed — skipping worktree cleanup")
    else:
        # Reload state (may have been modified by phase 1)
        state = load_state(state_file)
        change_names = {c.name for c in state.changes}
        # `paused` is recoverable, not terminal: the change has partial
        # progress (iteration counters, retry_context, committed work on the
        # branch) that the supervisor must be able to resume from. Dropping
        # its worktree + deleting its branch destroys that progress and the
        # committed code with it. Treat paused like other active statuses —
        # leave the worktree alone so the next dispatch can resume.
        active_statuses = {"running", "pending", "dispatched", "stalled", "paused"}

        # Parse worktree paths
        worktree_paths = []
        for line in wt_result.stdout.split("\n"):
            if line.startswith("worktree "):
                worktree_paths.append(line[9:].strip())

        for wt_path in worktree_paths:
            wt_basename = os.path.basename(wt_path)
            # Only consider worktrees matching <project>-wt-<name> pattern
            wt_prefix = f"{project_name}-wt-"
            if not wt_basename.startswith(wt_prefix):
                continue

            change_name = wt_basename[len(wt_prefix):]

            # Find corresponding change in state
            change = next((c for c in state.changes if c.name == change_name), None)

            should_remove = False
            reason = ""

            if change is None:
                # No state entry — orphaned
                should_remove = True
                reason = "no state entry"
            elif change.status in ("merged", "done"):
                # Change completed. HONOR the orchestration.yaml
                # `worktree_retention` policy here — the merger already
                # does the same for the fresh-after-merge path. Without
                # this, a monitor restart (e.g. after sentinel restart
                # or a new phase kicking off) treated "merged" as free
                # licence to force-remove, losing the preserved worktree
                # the user wanted to inspect.
                from .merger import _resolve_retention
                retention = _resolve_retention()
                if retention == "keep":
                    logger.debug(
                        "Worktree for %s (%s) kept per retention=keep",
                        change_name, change.status,
                    )
                    continue
                should_remove = True
                reason = f"status={change.status}, retention={retention}"
            elif change.status in active_statuses:
                # Active change — don't touch
                continue
            else:
                # Other statuses (failed, etc.) — check case by case
                should_remove = True
                reason = f"terminal status={change.status}"

            if not should_remove:
                continue

            # Safety: skip if worktree has uncommitted changes
            if os.path.isdir(wt_path):
                status_r = run_command(
                    ["git", "status", "--porcelain"],
                    timeout=10,
                    cwd=wt_path,
                )
                if status_r.exit_code == 0 and status_r.stdout.strip():
                    logger.warning("Skipping dirty worktree: %s (has uncommitted changes)", change_name)
                    continue

                # If a stale process is running in the worktree, kill it first
                # (only for terminal statuses — the change is done, the process is orphaned)
                if _has_process_in_dir(wt_path):
                    stale_pids = _find_pids_in_dir(wt_path)
                    if stale_pids:
                        logger.warning(
                            "Killing %d stale process(es) in worktree %s: %s",
                            len(stale_pids), change_name, stale_pids,
                        )
                        for pid in stale_pids:
                            try:
                                os.kill(pid, 15)  # SIGTERM
                            except OSError:
                                pass
                        time.sleep(1)
                    # Re-check after kill
                    if _has_process_in_dir(wt_path):
                        logger.warning("Skipping worktree %s: process still running after SIGTERM", change_name)
                        continue

            # Archive the worktree before git removes it. Renaming the dir
            # with a timestamp suffix preserves all uncommitted changes,
            # test-results/, and agent logs for post-mortem — `git worktree
            # remove --force` would delete everything on disk. After the
            # rename `git worktree prune` cleans up the stale admin entry
            # in the main repo's .git/worktrees/.
            archived_path = None
            if os.path.isdir(wt_path):
                archived_path = f"{wt_path}.removed.{int(time.time())}"
                try:
                    os.rename(wt_path, archived_path)
                    logger.info(
                        "Archived worktree before removal: %s -> %s",
                        change_name, archived_path,
                    )
                except OSError as exc:
                    logger.warning(
                        "Failed to archive worktree %s (%s) — falling back to destructive remove",
                        change_name, exc,
                    )
                    archived_path = None

            try:
                if archived_path:
                    # Worktree dir is gone (renamed). Prune the admin entry.
                    rm_r = run_command(
                        ["git", "worktree", "prune"],
                        timeout=30,
                        cwd=project_dir,
                    )
                else:
                    rm_r = run_command(
                        ["git", "worktree", "remove", "--force", wt_path],
                        timeout=30,
                        cwd=project_dir,
                    )
                if rm_r.exit_code == 0:
                    worktrees_removed += 1
                    logger.info("Removed orphaned worktree: %s (%s)", change_name, reason)
                    # Also delete the branch
                    run_command(
                        ["git", "branch", "-D", f"change/{change_name}"],
                        timeout=10,
                        cwd=project_dir,
                    )
                else:
                    logger.warning("Failed to remove worktree %s: %s", change_name, rm_r.stderr[:200])
            except Exception:
                logger.warning("Worktree removal failed for %s", change_name, exc_info=True)

    # ── Phase 3: Collect missing test artifacts ──
    # If a worktree has test-results but state has no artifacts, collect them now.
    # This catches cases where the merge pipeline didn't run (sentinel crash/timeout).
    artifacts_collected = 0
    try:
        from .profile_loader import load_profile as _lp_cleanup
        _cleanup_profile = _lp_cleanup()
        state = load_state(state_file)
        for change in state.changes:
            wt = change.worktree_path
            if not wt or not os.path.isdir(wt):
                continue
            if change.extras.get("test_artifacts"):
                continue  # already collected
            artifacts = _cleanup_profile.collect_test_artifacts(wt)
            if artifacts:
                images = [a for a in artifacts if a.get("type") == "image"]
                with locked_state(state_file) as _ast2:
                    _ch2 = next((c for c in _ast2.changes if c.name == change.name), None)
                    if _ch2:
                        _ch2.extras["test_artifacts"] = artifacts
                        _ch2.extras["e2e_screenshot_count"] = len(images)
                        if images:
                            _ch2.extras["e2e_screenshot_dir"] = os.path.dirname(os.path.dirname(images[0]["path"]))
                artifacts_collected += 1
                logger.info("Collected %d test artifacts for %s (missed by merger)", len(artifacts), change.name)
    except Exception:
        logger.debug("Artifact collection in cleanup failed (non-critical)", exc_info=True)

    # ── Phase 4: Release stuck issues whose fix_agent is dead ──
    # Observed on craftbrew-run-20260415-0146: an ISSUE in state="diagnosed"
    # or "fixing" with fix_agent_pid pointing to a process that died mid-fix
    # stays active forever. The merger queries _get_issue_owned_changes (which
    # includes those states) and silently skips the merge with "owned by issue
    # pipeline", blocking the change indefinitely. Without this phase the
    # user has to resolve the issues manually via the registry API.
    issues_released = _release_dead_fix_agent_issues(state_file)

    # Summary
    total = pids_cleared + steps_fixed + worktrees_removed + artifacts_collected + queue_restored + issues_released
    if total > 0:
        logger.info(
            "Orphan cleanup: %d worktrees removed, %d PIDs cleared, %d steps fixed, "
            "%d artifacts collected, %d merge queue entries restored, %d issues released",
            worktrees_removed, pids_cleared, steps_fixed, artifacts_collected,
            queue_restored, issues_released,
        )
    else:
        logger.debug("Orphan cleanup: nothing to clean")


def _release_dead_fix_agent_issues(state_file: str) -> int:
    """Auto-resolve active issues whose fix_agent_pid is dead.

    An issue with state in {investigating, fixing, diagnosed, awaiting_approval}
    and a dead fix_agent_pid is an orphaned issue — no one is going to progress
    it, but it blocks the merger for the affected change (merger calls
    `_get_issue_owned_changes` which includes those states). Transition such
    issues to `resolved` so the merge queue can proceed on the next cycle.

    Returns the number of issues auto-released.
    """
    try:
        state_dir = os.path.dirname(os.path.abspath(state_file))
        registry_path = os.path.join(state_dir, ".set", "issues", "registry.json")
        if not os.path.isfile(registry_path):
            return 0
        with open(registry_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return 0

    active_states = {"investigating", "fixing", "diagnosed", "awaiting_approval"}
    released = 0
    now_iso = datetime.now(timezone.utc).astimezone().isoformat()

    for issue in data.get("issues", []):
        if issue.get("state") not in active_states:
            continue
        pid = issue.get("fix_agent_pid")
        if not pid:
            # No fix agent started yet; leave alone.
            continue
        try:
            os.kill(int(pid), 0)
            # process still alive — leave alone
            continue
        except (ProcessLookupError, PermissionError, ValueError, OSError):
            # fix agent dead
            pass

        issue["state"] = "resolved"
        issue["resolved_at"] = now_iso
        issue["updated_at"] = now_iso
        issue["fix_agent_pid"] = None
        logger.warning(
            "Released stuck issue %s: fix_agent_pid=%s is dead, state was %s, "
            "affected_change=%s — auto-resolved so merge queue can proceed",
            issue.get("id"), pid, issue.get("state"), issue.get("affected_change"),
        )
        released += 1

    if released > 0:
        try:
            with open(registry_path, "w") as f:
                json.dump(data, f, indent=4)
        except OSError:
            logger.warning("Failed to persist released issues", exc_info=True)

    return released


def _cwd_in_dir(cwd: str, directory: str) -> bool:
    """Check if a CWD path is inside the given directory (exact or subdir)."""
    return cwd == directory or cwd.startswith(directory + os.sep)


def _find_pids_in_dir(directory: str) -> list[int]:
    """Find PIDs that have their CWD in the given directory."""
    pids = []
    proc_dir = "/proc"
    if not os.path.isdir(proc_dir):
        return pids
    try:
        for pid_entry in os.listdir(proc_dir):
            if not pid_entry.isdigit():
                continue
            try:
                cwd = os.readlink(f"/proc/{pid_entry}/cwd")
                if _cwd_in_dir(cwd, directory):
                    pids.append(int(pid_entry))
            except (OSError, PermissionError):
                continue
    except OSError:
        pass
    return pids


def _has_process_in_dir(directory: str) -> bool:
    """Check if any process has its CWD in the given directory.

    Uses /proc on Linux. Returns False on non-Linux or if check fails.
    """
    proc_dir = "/proc"
    if not os.path.isdir(proc_dir):
        return False  # Not Linux — can't check, assume safe

    try:
        for pid_entry in os.listdir(proc_dir):
            if not pid_entry.isdigit():
                continue
            try:
                cwd = os.readlink(f"/proc/{pid_entry}/cwd")
                if _cwd_in_dir(cwd, directory):
                    return True
            except (OSError, PermissionError):
                continue
    except OSError:
        pass
    return False


# ─── Monitor Loop ──────────────────────────────────────────────────


def check_config_drift(state_file: str, directives_json: str, *, event_bus: Any = None) -> bool:
    """Warn when `config.yaml` is newer than the parsed `directives.json`.

    The orchestrator parses `directives.json` at startup. When the user edits
    `config.yaml` after startup without restarting the supervisor, gate
    behavior diverges silently from the file the user believes is authoritative
    — a classic "I changed the config and nothing happened" footgun.

    Returns True when drift was detected, False otherwise. Safe to call in a
    broad try-block; never raises.
    """
    try:
        state_dir = os.path.dirname(os.path.abspath(state_file))
        cfg_path = os.path.join(state_dir, "set", "orchestration", "config.yaml")
        directives_file = directives_json if os.path.isfile(directives_json) else None
        if not directives_file or not os.path.isfile(cfg_path):
            return False
        cfg_mtime = os.path.getmtime(cfg_path)
        dir_mtime = os.path.getmtime(directives_file)
        if cfg_mtime <= dir_mtime:
            return False
        delta = int(cfg_mtime - dir_mtime)
        logger.warning(
            "CONFIG_DRIFT: config.yaml (mtime=%d) is newer than directives.json "
            "(mtime=%d) by %d seconds — restart the supervisor to pick up "
            "config edits. path=%s",
            int(cfg_mtime), int(dir_mtime), delta, cfg_path,
        )
        if event_bus is not None:
            try:
                event_bus.emit(
                    "CONFIG_DRIFT",
                    data={
                        "config_yaml": cfg_path,
                        "directives_json": directives_file,
                        "config_mtime": int(cfg_mtime),
                        "directives_mtime": int(dir_mtime),
                        "delta_seconds": delta,
                    },
                )
            except Exception:
                logger.debug("CONFIG_DRIFT event emit failed", exc_info=True)
        return True
    except Exception:
        logger.debug("CONFIG_DRIFT check failed (non-critical)", exc_info=True)
        return False


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

    # Auto-regenerate directives.json when config.yaml is newer — the user
    # edits config.yaml and restarts the supervisor expecting the change to
    # take effect, but without this regen the orchestrator keeps using the
    # stale directives.json (observed: a 90m iteration_timeout edit never
    # took effect for ~18h on craftbrew-run-20260415-0146 because restart
    # didn't refresh directives). We regenerate eagerly at startup so the
    # user's "edit + restart" contract actually holds.
    try:
        _state_dir = os.path.dirname(os.path.abspath(state_file))
        _cfg_path = os.path.join(_state_dir, "set", "orchestration", "config.yaml")
        if (
            os.path.isfile(_cfg_path)
            and os.path.isfile(directives_json)
            and os.path.getmtime(_cfg_path) > os.path.getmtime(directives_json)
        ):
            _state_tmp = load_state(state_file)
            _input_path = (
                _state_tmp.extras.get("input_path")
                or _state_tmp.extras.get("spec_path")
            )
            if not _input_path:
                from .paths import LineagePaths as _LP_init
                _plan_path = _LP_init.from_state_file(state_file).plan_file
                if os.path.isfile(_plan_path):
                    try:
                        with open(_plan_path) as _pf:
                            _plan = json.load(_pf)
                        _input_path = _plan.get("input_path")
                    except Exception:
                        _input_path = None
            if _input_path and os.path.exists(_input_path):
                from .config import resolve_directives as _resolve_directives
                _new = _resolve_directives(_input_path, config_path=_cfg_path)
                with open(directives_json, "w") as _df:
                    json.dump(_new, _df, indent=2)
                logger.info(
                    "Regenerated directives.json from config.yaml (input=%s)",
                    _input_path,
                )
            else:
                logger.warning(
                    "CONFIG_DRIFT detected but cannot regenerate directives — "
                    "no input_path in state/plan; supervisor will keep stale directives"
                )
    except Exception:
        logger.debug("directives auto-regen failed (non-fatal)", exc_info=True)

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

    # Surface config drift (config.yaml edited after directives.json parsed).
    # After the auto-regen above this should be a no-op; kept for cases where
    # regen was skipped (missing input_path) so the user still sees the warn.
    check_config_drift(state_file, directives_json, event_bus=event_bus)

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

    # Sync module-level event_bus to the per-project events file so that
    # run_claude_logged() LLM_CALL events land in the same file the API reads.
    try:
        from .events import event_bus as _module_bus
        if event_bus and event_bus.log_path and _module_bus.log_path != event_bus.log_path:
            _module_bus._log_path = event_bus.log_path
            logger.debug("Synced module event_bus to %s", event_bus.log_path)
    except Exception:
        pass

    # Restore active_seconds from state (cumulative across restarts)
    state = load_state(state_file)
    active_seconds = state.extras.get("active_seconds", 0)
    token_wait = False
    replan_retry_count = 0

    # Refuse to start if orchestration is already complete — prevents
    # sentinel restart from re-dispatching all changes from scratch
    if state.status == "done":
        logger.info("Orchestration already done — refusing to start. Use --force to override.")
        lock_fd.close()
        return

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

    # Clean orphaned resources from previous crash/restart
    try:
        _cleanup_orphans(state_file)
    except Exception:
        logger.warning("Orphan cleanup failed (non-critical)", exc_info=True)

    # Auto-resume changes paused by the previous shutdown. Engine.shutdown()
    # parks in-flight changes as "paused" with the comment "so they resume
    # on restart", but the dispatch loop EXCLUDES paused from ready-to-
    # dispatch. Without this step, a sentinel restart (force-kill after 90s
    # grace) permanently parks active changes until the user manually
    # POSTs /api/.../resume. See dispatcher.resume_paused_changes.
    try:
        from .dispatcher import resume_paused_changes
        _resumed = resume_paused_changes(state_file, event_bus=event_bus)
        if _resumed:
            logger.info(
                "Auto-resumed %d change(s) paused by prior shutdown",
                _resumed,
            )
    except Exception:
        logger.warning("Paused-change auto-resume failed (non-critical)", exc_info=True)

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

        # Issue diagnosed-timeout watchdog (every ~10 polls ≈ 2.5 minutes).
        # Non-blocking: failure logs a warning and continues.
        if poll_count % 10 == 0:
            try:
                from .issues.watchdog import check_diagnosed_timeouts

                check_diagnosed_timeouts(
                    Path(os.path.dirname(os.path.abspath(state_file))),
                    event_bus=event_bus,
                )
            except Exception:
                logger.debug(
                    "Diagnosed-timeout watchdog failed (non-blocking)",
                    exc_info=True,
                )

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

        # Idle detection (activity-timeline instrumentation)
        from .watchdog import check_idle
        check_idle(state.to_dict(), event_bus=event_bus)

        # Completion detection
        if _check_completion(state_file, d, event_bus):
            break


# ─── Poll Helpers ──────────────────────────────────────────────────

def _verify_gates_already_passed(change: Any) -> bool:
    """Return True if all blocking verify gates have already passed.

    Used on monitor restart to detect changes in "verifying" / "integrating"
    status where the gates completed successfully but the monitor died before
    queuing the merge (Bug #5b). Any blocking gate result of "fail" or
    "critical" → False. A gate with no result (None) → False (gates haven't
    run yet).

    Gate results live in two places: dataclass fields (test/build/review/
    e2e/smoke) and the extras dict (scope_check, spec_coverage, rules, etc.).
    scope_check has been written under both "scope_check" and
    "scope_check_result" over time — accept either.
    """
    _PASS_VALUES = {"pass", "skipped", "warn-fail"}
    _FAIL_VALUES = {"fail", "critical"}

    extras = change.extras or {}

    scope_check = extras.get("scope_check") or extras.get("scope_check_result")

    gate_results = [
        change.test_result,
        change.build_result,
        change.review_result,
        change.e2e_result,  # dataclass field, NOT extras
        scope_check,
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
        except Exception as _e:
            logger.debug("Watchdog event emit failed: %s", _e)
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


def _has_commits_since_gate(wt_path: str, last_gate_commit: str) -> bool:
    """Check if worktree has new commits since the last gate run.

    Used to decide whether a stopped/stuck ralph loop made progress worth
    re-gating, vs. marking the change as stalled.
    """
    if not os.path.isdir(wt_path):
        return False
    if not last_gate_commit:
        return True  # no baseline → assume progress
    try:
        result = subprocess.run(
            ["git", "-C", wt_path, "log", f"{last_gate_commit}..HEAD", "--oneline"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return True  # invalid ref or git error → assume progress (safe)
        return bool(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return True  # on error, assume progress (safe: triggers re-gate not stall)


def _apply_stuck_loop_counter(
    state_file: str,
    change_name: str,
    max_stuck_loops: int,
    event_bus: Any,
) -> bool:
    """Advance the stuck-loop circuit breaker for a change that just exited stuck.

    Rules (see retry-loop-completion spec):
      - If `last_gate_fingerprint` is unset, the verifier hasn't written a
        gate verdict yet → leave counter untouched and return False.
      - Load the last observed fingerprint from `extras["stuck_fingerprint"]`.
      - **Threshold-first**: if counter + 1 would reach `max_stuck_loops`
        AND fingerprint matches the prior one, escalate (mark failed +
        fire fix-iss) and return True — the caller skips re-gate routing.
      - Otherwise: if fingerprint matches, increment; if it changed, reset
        to 0 and record the new fingerprint.

    Returns True when the circuit breaker fires (hard-fail + escalation).
    """
    with locked_state(state_file) as state:
        change = None
        for c in state.changes:
            if c.name == change_name:
                change = c
                break
        if change is None:
            return False

        current_fp = change.last_gate_fingerprint
        if not current_fp:
            logger.debug(
                "stuck-loop counter: %s has no last_gate_fingerprint — skipping",
                change_name,
            )
            return False

        prior_fp = change.extras.get("stuck_fingerprint") if change.extras else None
        prior_count = int(change.stuck_loop_count or 0)

        # Threshold-first ordering (tasks.md 3.3): if the fingerprint has
        # changed THIS iteration, reset wins — the breaker does not fire even
        # if counter would otherwise reach max. If fingerprint is unchanged
        # (or no prior recorded), increment; fire when we reach the max.
        fingerprint_stable = prior_fp is None or prior_fp == current_fp
        new_count = (prior_count + 1) if fingerprint_stable else 0
        would_trip = fingerprint_stable and new_count >= max_stuck_loops

        change.stuck_loop_count = new_count
        change.extras["stuck_fingerprint"] = current_fp

        _escalate_pending = False
        if would_trip:
            change.status = "failed:stuck_no_progress"
            logger.error(
                "Stuck-loop circuit breaker FIRED for %s: %d consecutive stuck "
                "exits with identical fingerprint %s — escalating to fix-iss",
                change_name, new_count, current_fp,
            )
            if event_bus:
                event_bus.emit(
                    "STUCK_LOOP_ESCALATED",
                    change=change_name,
                    data={
                        "stuck_loop_count": new_count,
                        "fingerprint": current_fp,
                        "max_stuck_loops": max_stuck_loops,
                    },
                )
            _escalate_pending = True
        elif fingerprint_stable:
            logger.info(
                "stuck-loop counter for %s: %d/%d (fingerprint unchanged %s)",
                change_name, new_count, max_stuck_loops, current_fp,
            )
        else:
            logger.info(
                "stuck-loop counter for %s: reset to 0 (fingerprint changed %s → %s)",
                change_name, prior_fp, current_fp,
            )

    if _escalate_pending:
        try:
            from .issues.manager import escalate_change_to_fix_iss
            escalate_change_to_fix_iss(
                state_file=state_file,
                change_name=change_name,
                stop_gate="",
                findings=[],
                escalation_reason="stuck_no_progress",
                event_bus=event_bus,
            )
        except Exception:
            logger.warning(
                "escalate_change_to_fix_iss failed for %s (stuck_no_progress)",
                change_name, exc_info=True,
            )
        return True
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
                    # Agent completed successfully — let poll_change() handle it.
                    # poll_change reads loop-state, detects done, calls handle_change_done()
                    # which runs the full gate pipeline (review, rules, spec_verify, etc.)
                    # before adding to merge queue. Agent being dead is fine.
                    logger.info(
                        "Change %s: agent finished (loop_status=done) — routing to verifier pipeline",
                        change.name,
                    )
                    _resolve_issues_for_change(change.name)
                    if event_bus:
                        event_bus.emit("CHANGE_DONE", change=change.name)
                    # Fall through to poll_change() below — do NOT mark done or continue

                elif ls_status in ("stopped", "stuck"):
                    # Agent exited fix loop (not "done" but made an attempt).
                    # Check for new commits — if the agent committed fixes,
                    # re-gate immediately instead of waiting for stall timeout.
                    last_gate = (change.extras or {}).get("last_gate_commit", "")
                    has_progress = _has_commits_since_gate(wt_path, last_gate)
                    if has_progress:
                        # Stuck-loop circuit breaker: consult the current
                        # last_gate_fingerprint (written by the verifier). If
                        # it matches the fingerprint from the PRIOR stuck exit,
                        # increment stuck_loop_count; threshold check BEFORE
                        # reset (so simultaneous threshold+fingerprint-changed
                        # lets the fingerprint change win → counter resets).
                        if ls_status == "stuck":
                            fired = _apply_stuck_loop_counter(
                                state_file, change.name, d.max_stuck_loops, event_bus,
                            )
                            if fired:
                                # Change was hard-failed + escalated to fix-iss.
                                # Skip the re-gate routing.
                                continue

                        logger.info(
                            "Change %s: agent exited fix loop (loop_status=%s) with new commits "
                            "— routing to re-gate (skip stall timeout)",
                            change.name, ls_status,
                        )
                        _resolve_issues_for_change(change.name)
                        if event_bus:
                            event_bus.emit("CHANGE_DONE", change=change.name)
                        # Fall through to poll_change() → handle_change_done() → re-gate
                    else:
                        logger.warning(
                            "Change %s: agent exited fix loop (loop_status=%s) with NO new commits "
                            "— marking stalled",
                            change.name, ls_status,
                        )
                        update_change_field(state_file, change.name, "status", "stalled")
                        update_change_field(state_file, change.name, "stalled_at", int(time.time()))
                        if event_bus:
                            event_bus.emit("CHANGE_STALLED", change=change.name,
                                           data={"reason": f"fix_loop_no_progress_{ls_status}"})
                        continue

                else:
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
                )
        except Exception:
            logger.debug("Failed to parse loop-state for %s", change.name, exc_info=True)


# ─── Recovery ──────────────────────────────────────────────────────


# Fields cleared when a failed change is reset back to pending.
# Anything not in this set survives the reset (scope, depends_on, phase, etc.).
_RESET_FAILED_FIELDS: dict[str, Any] = {
    "status": "pending",
    "worktree_path": None,
    "ralph_pid": None,
    "current_step": "",
    "verify_retry_count": 0,
    "gate_retry_count": 0,
    "redispatch_count": 0,
    "merge_retry_count": 0,
    "integration_e2e_retry_count": 0,
    "verify_retry_tokens": 0,
    "gate_retry_tokens": 0,
    "test_result": None,
    "build_result": None,
    "e2e_result": None,
    "review_result": None,
    "smoke_result": None,
    "smoke_e2e_result": None,
    "scope_check_result": None,
    "e2e_coverage_result": None,
    "rules_result": None,
    "lint_result": None,
    "spec_coverage_result": None,
    "integration_gate_fail": "",
    "failure_reason": "",
}


def _build_reset_retry_context(change: Any, wt_path: str) -> str:
    """Build the retry_context injected by reset_failed_changes.

    This is the user-facing prompt the agent sees on its next iteration. The
    framing matters: we need the agent to understand that (a) its previous
    implementation is still on disk in the worktree, (b) the retry budget
    was raised so it has fresh attempts, and (c) it MUST fix incrementally
    rather than scrap-and-rewrite. Earlier runs showed that without this
    framing, the agent would run `/opsx:ff` and recreate every artifact,
    burning 80k+ tokens on work it had already done.

    Pulls from the change's recorded gate outputs. Only sections with
    content are included — keeps the prompt under ~5KB for big contexts.
    """
    sections: list[str] = [
        "# Retry with raised verify budget",
        "",
        "Your previous attempts on this change hit the verify retry cap. "
        "The cap has been raised and your prior work has been preserved — "
        "this is NOT a fresh dispatch.",
        "",
        "## How to proceed",
        "",
        "1. **DO NOT run `/opsx:ff`, `/opsx:new`, or recreate `proposal.md`, "
        "`tasks.md`, or spec files.** They already exist in "
        "`openspec/changes/<this-change>/` from your earlier iteration. "
        "Recreating them wastes the token budget and loses context.",
        "2. **DO NOT rewrite implementation files from scratch.** Your "
        "previous commits are in this worktree's branch. Run `git log "
        "--oneline main..HEAD` and `git diff --stat main..HEAD` first to "
        "see what you built.",
        "3. **Fix the specific gate failure below.** The e2e / review / "
        "build output shows exactly what's wrong. Target it surgically.",
        "4. If the prior implementation is fundamentally misconceived and "
        "an incremental fix is impossible, say so explicitly in your "
        "first message and explain — don't silently start over.",
        "",
    ]

    # --- Git history from the preserved worktree ---
    if wt_path and os.path.isdir(wt_path):
        try:
            from .subprocess_utils import run_command as _run
            log_r = _run(["git", "log", "--oneline", "main..HEAD"], cwd=wt_path, timeout=10)
            if log_r.exit_code == 0 and log_r.stdout.strip():
                lines = log_r.stdout.strip().splitlines()
                git_log = "\n".join(lines[:30])
                if len(lines) > 30:
                    git_log += f"\n... and {len(lines) - 30} more commits"
                sections.append(f"## Your previous commits\n\n```\n{git_log}\n```\n")
            stat_r = _run(["git", "diff", "--stat", "main..HEAD"], cwd=wt_path, timeout=10)
            if stat_r.exit_code == 0 and stat_r.stdout.strip():
                lines = stat_r.stdout.strip().splitlines()
                git_stat = "\n".join(lines[:60])
                if len(lines) > 60:
                    git_stat += f"\n... and {len(lines) - 60} more files"
                sections.append(f"## Files you already changed\n\n```\n{git_stat}\n```\n")
        except Exception as _e:
            logger.debug("_build_reset_retry_context: git history extract failed: %s", _e)

    # --- Last gate outputs (truncated) ---
    extras = getattr(change, "extras", {}) or {}

    def _section(title: str, body: str, limit: int = 3000) -> None:
        if not body:
            return
        snippet = smart_truncate_structured(body, limit)
        sections.append(f"## {title}\n\n```\n{snippet}\n```\n")

    # Structured findings block — when any prior gate emitted a verdict with
    # `findings: [...]`, render FILE/LINE/FIX verbatim BEFORE the raw outputs.
    # The agent scans top-down; putting concrete fix instructions above the
    # raw log reduces the chance of re-diagnosing from scratch. See OpenSpec
    # change: fix-e2e-infra-systematic (T2.1).
    try:
        from .findings import findings_from_dicts, render_findings_block
        findings_raw = extras.get("findings") or []
        findings_objs = findings_from_dicts(findings_raw)
        if findings_objs:
            sections.append("## Structured findings (from last verdict)")
            sections.append(render_findings_block(findings_objs, limit=30))
    except Exception:
        logger.debug("findings render skipped", exc_info=True)

    # Budgets bumped to 30-40K for review/e2e — these are reset-path retry
    # prompts for changes that hit the retry cap. Tight 2-4K budgets drop
    # FILE/LINE/FIX pairings mid-finding, which is what caused repeated
    # impl cycles on the same (misdiagnosed) bug. See OpenSpec change:
    # fix-retry-context-signal-loss (Bug D audit).
    e2e_output = extras.get("e2e_output") or ""
    if e2e_output:
        _section("Last e2e gate output", e2e_output, limit=30_000)
    else:
        e2e_result = getattr(change, "e2e_result", None)
        if e2e_result and e2e_result != "pass":
            sections.append(f"## Last e2e gate result\n\n`{e2e_result}` (no captured output — check `.set/logs/`).\n")

    review_output = extras.get("review_output") or ""
    if review_output:
        _section("Last review output", review_output, limit=30_000)

    build_output = extras.get("build_output") or ""
    if build_output:
        # Build errors are usually concise (stacktrace + offending file).
        # Smaller budget is fine.
        _section("Last build output", build_output, limit=5_000)

    test_output = extras.get("test_output") or ""
    if test_output:
        _section("Last test output", test_output, limit=10_000)

    failure_reason = getattr(change, "failure_reason", "") or extras.get("failure_reason", "")
    if failure_reason:
        sections.append(f"## Recorded failure reason\n\n{failure_reason[:1500]}\n")

    sections.append(
        "## Summary of what to do first\n\n"
        "Read the gate output above, inspect the files you already wrote "
        "(git log + git diff), and make the minimal change that turns the "
        "failing gate green. If the e2e suite is timing out, focus on "
        "reducing per-test wait time or splitting the suite — do NOT "
        "rewrite unrelated working code.",
    )

    return "\n".join(sections)


def reset_failed_changes(
    state_file: str,
    *,
    event_bus: Any = None,
    destroy_worktree: bool = False,
) -> list[str]:
    """Reset all `failed`/`integration-failed` changes back to `pending`.

    Used by the sentinel/start `reset_failed=true` path so the user can resume
    a stopped run after raising the retry cap or fixing root-cause issues.

    Default behavior preserves the existing worktree + branch + artifacts so
    the next dispatch resumes the agent's prior work with a freshly-built
    `retry_context` explaining what failed. This is the intended path: the
    agent keeps the spec artifacts (`openspec/changes/<name>/`) and the
    implementation in the worktree, and incrementally fixes the specific
    gate failure — NOT a full rewrite from scratch (which was the bug
    pre-2026-04-14: destroying the worktree forced `/opsx:ff` to recreate
    artifacts, discarding work and looking like a regression from the
    agent's perspective).

    Set `destroy_worktree=True` only when the worktree is known-corrupt
    (merge conflicts that cannot be auto-resolved, filesystem damage, or
    explicit user request to start over). In that mode the worktree is
    harvested to the orchestration archive before removal.

    Steps:
    1. Build `retry_context` from the last gate outputs (e2e, review, etc.)
       with an explicit "incremental fix, do NOT rewrite" directive.
    2. If `destroy_worktree`: harvest + `git worktree remove --force` +
       branch delete. Otherwise: log archive only, preserve worktree.
    3. Reset state fields per `_RESET_FAILED_FIELDS` (but keep retry_context
       so the next dispatch consumes it in input.md).
    4. Clear top-level `status=stopped` / `stop_reason=dep_blocked`.

    Returns the list of reset change names.
    """
    from .state import WatchdogState
    from .subprocess_utils import run_command as _run

    state = load_state(state_file)
    targets = [
        c for c in state.changes
        if c.status in ("failed", "integration-failed")
    ]
    if not targets:
        logger.info("reset_failed_changes: no failed changes to reset")
        return []

    project_dir = os.path.dirname(state_file)
    reset_names: list[str] = []

    for change in targets:
        wt_path = change.worktree_path or ""
        logger.info(
            "reset_failed_changes: resetting %s (was %s, wt=%s, destroy=%s)",
            change.name, change.status, wt_path or "<none>", destroy_worktree,
        )

        # 1. Build retry_context from the last failure outputs BEFORE touching
        #    the worktree — we need git history and file state to still exist.
        retry_ctx = _build_reset_retry_context(change, wt_path)

        if destroy_worktree:
            # 2a. Harvest + remove when explicitly requested
            if wt_path and os.path.isdir(wt_path):
                try:
                    from .worktree_harvest import harvest_worktree
                    harvest_worktree(change.name, wt_path, project_dir, reason="reset_failed")
                except Exception:
                    logger.warning(
                        "reset_failed_changes: harvest failed for %s",
                        change.name, exc_info=True,
                    )
                branch = ""
                br = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=wt_path, timeout=10)
                if br.exit_code == 0:
                    branch = br.stdout.strip()
                rm = _run(["git", "worktree", "remove", "--force", wt_path], cwd=project_dir, timeout=30)
                if rm.exit_code != 0:
                    logger.warning(
                        "reset_failed_changes: git worktree remove failed for %s (%s) — falling back to rm",
                        change.name, rm.stderr.strip()[:200],
                    )
                    import shutil
                    shutil.rmtree(wt_path, ignore_errors=True)
                if branch and branch not in ("HEAD", "main", "master"):
                    _run(["git", "branch", "-D", branch], cwd=project_dir, timeout=10)
        else:
            # 2b. Preserve worktree. Only archive logs (non-destructive).
            if wt_path and os.path.isdir(wt_path):
                try:
                    from .merger import _archive_worktree_logs
                    _archive_worktree_logs(change.name, wt_path)
                except Exception:
                    logger.debug(
                        "reset_failed_changes: log archive failed for %s",
                        change.name, exc_info=True,
                    )

        # 3. Reset state fields — but NOT worktree_path when preserving it
        for fname, fvalue in _RESET_FAILED_FIELDS.items():
            if not destroy_worktree and fname == "worktree_path":
                continue
            try:
                update_change_field(state_file, change.name, fname, fvalue, event_bus=event_bus)
            except Exception:
                logger.debug(
                    "reset_failed_changes: could not reset %s.%s",
                    change.name, fname, exc_info=True,
                )

        # 3b. Inject the retry_context so the next dispatch consumes it.
        if retry_ctx:
            try:
                update_change_field(state_file, change.name, "retry_context", retry_ctx, event_bus=event_bus)
                logger.info(
                    "reset_failed_changes: set retry_context for %s (%d chars)",
                    change.name, len(retry_ctx),
                )
            except Exception:
                logger.warning(
                    "reset_failed_changes: could not set retry_context for %s",
                    change.name, exc_info=True,
                )

        # 4. Reset watchdog
        with locked_state(state_file) as st:
            ch = next((c for c in st.changes if c.name == change.name), None)
            if ch is not None:
                ch.watchdog = WatchdogState(
                    last_activity_epoch=int(time.time()),
                    action_hash_ring=[],
                    consecutive_same_hash=0,
                    escalation_level=0,
                    progress_baseline=0,
                )

        if event_bus:
            try:
                event_bus.emit("CHANGE_RESET_FAILED", change=change.name, data={"prev_status": change.status})
            except Exception:
                pass

        reset_names.append(change.name)

    # 5. Clear top-level stopped status so the monitor will resume cleanly
    try:
        cur = load_state(state_file)
        if cur.status == "stopped":
            update_state_field(state_file, "status", "running", event_bus=event_bus)
        if cur.extras.get("stop_reason"):
            update_state_field(state_file, "stop_reason", "", event_bus=event_bus)
        if cur.extras.get("dep_blocked_count"):
            update_state_field(state_file, "dep_blocked_count", 0, event_bus=event_bus)
    except Exception:
        logger.warning("reset_failed_changes: could not clear top-level stop fields", exc_info=True)

    logger.info(
        "reset_failed_changes: reset %d change(s): %s",
        len(reset_names), ", ".join(reset_names),
    )
    return reset_names


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
                        f"Build output:\n{smart_truncate_structured(build_output, 2000)}\n\n"
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
    except Exception as _e:
        logger.debug("Git diff for test classification failed: %s", _e)

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
    except Exception as _e:
        logger.debug("Git history extraction failed: %s", _e)

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

    # --- Raw E2E Output (bumped from 2K for tail-preservation of Playwright
    # assertion errors and stack traces — see Bug D audit) ---
    if e2e_output:
        sections.append(
            f"### Test Output\n{smart_truncate_structured(e2e_output, 30_000)}\n"
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
        if change.status not in ("integration-e2e-failed", "integration-coverage-failed"):
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
        _is_coverage = change.status == "integration-coverage-failed"
        if _is_coverage:
            logger.info(
                "Recovering coverage-failed %s — redispatching agent for missing tests",
                change.name,
            )
        else:
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
        if c.status in ("done", "skipped")
        or (c.status == "merged" and c.current_step in ("done", None))
    )
    # Changes that are "merged" but still doing post-merge work (step != done)
    # should not count as complete — the merger sets status=merged before
    # post-merge steps finish (deps, hooks, coverage, artifact collection,
    # worktree cleanup). Counting them as complete causes premature exit.
    post_merge_active = sum(
        1 for c in state.changes
        if c.status == "merged" and c.current_step not in ("done", None)
    )
    if post_merge_active > 0:
        logger.debug(
            "%d changes still in post-merge processing (not yet step=done)",
            post_merge_active,
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

    Reads the issues registry (LineagePaths.issues_registry). Changes
    with active issues (investigating/fixing/awaiting_approval) should
    not be retried or redispatched by the orchestrator — the issue
    pipeline handles them.
    """
    from .paths import LineagePaths as _LP_iss
    registry_path = _LP_iss(os.getcwd()).issues_registry
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
        now_iso = datetime.now(timezone.utc).astimezone().isoformat()
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
    logger.debug("Gap check: digest_dir=%s, exists=%s", digest_dir, os.path.isdir(digest_dir))
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
        from .paths import LineagePaths as _LP_df
        _default_plan = _LP_df.from_state_file(state_file).plan_file
        plan_file = os.environ.get("PLAN_FILENAME", _default_plan)
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

    # 0. Rotate event streams BEFORE anything else so cycle N's history is
    #    sealed under `*-cycleN.jsonl` and the new cycle starts with an
    #    empty live file (Section 1.2 of run-history-and-phase-continuity).
    _rotate_event_streams(state_file, reason="replan")

    # 1. Archive completed changes to the lineage archive (LineagePaths.state_archive)
    _archive_completed_to_jsonl(state_file)

    # 2. Collect replan context
    replan_ctx = collect_replan_context(state_file)
    if not replan_ctx.get("completed_names"):
        logger.warning("Replan: no completed changes found — nothing to build on")
        return "no_new_work"

    # 3. Read plan metadata for input_mode/input_path
    from .paths import LineagePaths as _LP_rp
    _default_plan = _LP_rp.from_state_file(state_file).plan_file
    plan_file = os.environ.get("PLAN_FILENAME", _default_plan)
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
    from .paths import LineagePaths as _LP_replan
    domains_file = _LP_replan.from_state_file(state_file).plan_domains_file
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
        logger.debug("Replan: digest_dir=%s, exists=%s", digest_dir, os.path.isdir(digest_dir))
        domain_data = _load_domain_data(digest_dir)
        model = d.default_model or "opus"

        if replan_trigger == "spec_change":
            # Full re-decompose
            logger.info("Replan: full re-decompose (spec changed)")
            saved_brief = _phase1_planning_brief(domain_data, model=model)
            saved_domain_plans = _phase2_parallel_decompose(domain_data, saved_brief, model=model, digest_dir=digest_dir)
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
                    _dreq_ids = [r.get("id", "") for r in domain.get("requirements", [])]
                    saved_domain_plans[dname] = _decompose_single_domain(
                        domain, json.dumps(saved_brief), domain_data["conventions"], model=model,
                        test_plan_context=_build_test_plan_context(digest_dir, _dreq_ids),
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
                    _dreq_ids2 = [r.get("id", "") for r in domain.get("requirements", [])]
                    saved_domain_plans[dname] = _decompose_single_domain(
                        domain, json.dumps(saved_brief), domain_data["conventions"], model=model,
                        test_plan_context=_build_test_plan_context(digest_dir, _dreq_ids2),
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
        digest_dir=digest_dir,
    )

    if event_bus:
        event_bus.emit("REPLAN_DISPATCHED", data={"cycle": cycle, "changes": len(new_changes)})

    return "dispatched"


def _append_changes_to_state(state_file: str, new_changes: list[dict]) -> None:
    """Append new plan changes to existing orchestration state.

    Section 6 of run-history-and-phase-continuity moved phase-offset
    computation to plan-write time (`enrich_plan_metadata`).  By the time
    a plan reaches this function its `phase` values are already shifted
    to continue monotonically within the lineage, so this function
    appends them verbatim and only propagates lineage attribution.
    """
    from .state import Change, locked_state

    with locked_state(state_file) as state:
        existing_names = {c.name for c in state.changes}

        # Section 7.4: sentinel_session_id is preserved across replan —
        # we do NOT mint a fresh id here; the running session keeps its
        # identity.  Lineage is propagated unchanged.
        live_lineage = state.spec_lineage_id
        live_session = state.sentinel_session_id
        live_session_started = state.sentinel_session_started_at
        added = 0
        added_phases: list[int] = []
        for c in new_changes:
            if c.get("name") in existing_names:
                continue
            phase = c.get("phase", 1)
            change = Change(
                name=c["name"],
                scope=c.get("scope", ""),
                complexity=c.get("complexity", "M"),
                change_type=c.get("change_type", "feature"),
                depends_on=c.get("depends_on", []),
                roadmap_item=c.get("roadmap_item", ""),
                model=c.get("model", None),
                phase=phase,
                gate_hints=c.get("gate_hints") or None,
                requirements=c.get("requirements") or None,
                also_affects_reqs=c.get("also_affects_reqs") or None,
                spec_lineage_id=live_lineage,
                sentinel_session_id=live_session,
                sentinel_session_started_at=live_session_started,
            )
            state.changes.append(change)
            added += 1
            added_phases.append(phase)
        # Register new phases in the phases dict
        if added:
            phases_dict = state.extras.get("phases", {})
            for p in added_phases:
                p_key = str(p)
                if p_key not in phases_dict:
                    phases_dict[p_key] = {
                        "status": "pending",
                        "tag": None,
                        "server_port": None,
                        "server_pid": None,
                        "completed_at": None,
                    }
            state.extras["phases"] = phases_dict
            logger.info(
                "Appended %d new changes to state (phases: %s, lineage=%s)",
                added, sorted(phases_dict.keys()), live_lineage,
            )


def _next_cycle_index(orch_dir: str) -> int:
    """Return the next free `cycleN` integer for rotated event files.

    Inspects both `orchestration-events-cycle*.jsonl` and the state-events
    sibling so the two streams stay in sync.
    """
    import glob as _glob
    import re as _re

    cycle_re = _re.compile(r"-cycle(\d+)\.jsonl$")
    seen: set[int] = set()
    for pattern in (
        "orchestration-events-cycle*.jsonl",
        "orchestration-state-events-cycle*.jsonl",
    ):
        for path in _glob.glob(os.path.join(orch_dir, pattern)):
            m = cycle_re.search(os.path.basename(path))
            if m:
                seen.add(int(m.group(1)))
    return (max(seen) + 1) if seen else 1


def _rotate_event_streams(state_file: str, reason: str = "rotate") -> Optional[int]:
    """Seal the current event streams as `*-cycleN.jsonl` and start fresh ones.

    Section 1 of run-history-and-phase-continuity: rotation is best-effort —
    any OSError is logged at WARNING and the caller continues. The new
    rotated files get a `CYCLE_HEADER` line as their first record so
    downstream readers can group events by lineage / session / cycle.

    Returns the cycle index assigned to the rotated files, or None if
    there was nothing to rotate (live files absent or empty).
    """
    from .paths import LineagePaths
    lp = LineagePaths.from_state_file(state_file)
    orch_dir = lp.orchestration_dir
    live_events = lp.events_file
    live_state_events = lp.state_events_file

    have_events = os.path.exists(live_events) and os.path.getsize(live_events) > 0
    have_state_events = (
        os.path.exists(live_state_events) and os.path.getsize(live_state_events) > 0
    )
    if not have_events and not have_state_events:
        logger.debug("rotate_event_streams: nothing to rotate (live streams empty)")
        return None

    cycle_n = _next_cycle_index(orch_dir)
    rotated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="milliseconds")

    # Read lineage + session from the live state to stamp the header.
    spec_lineage_id: Optional[str] = None
    sentinel_session_id: Optional[str] = None
    plan_version: int = 1
    try:
        state = load_state(state_file)
        spec_lineage_id = state.spec_lineage_id
        sentinel_session_id = state.sentinel_session_id
        plan_version = state.plan_version
    except (StateCorruptionError, OSError):
        logger.debug("rotate_event_streams: state unreadable, header lineage will be null")

    header = {
        "type": "CYCLE_HEADER",
        "ts": rotated_at,
        "cycle": cycle_n,
        "reason": reason,
        "spec_lineage_id": spec_lineage_id,
        "sentinel_session_id": sentinel_session_id,
        "plan_version": plan_version,
    }
    header_line = json.dumps(header) + "\n"

    def _rotate_one(live_path: str, suffix: str) -> None:
        if not (os.path.exists(live_path) and os.path.getsize(live_path) > 0):
            return
        rotated = os.path.join(orch_dir, f"{suffix}-cycle{cycle_n}.jsonl")
        try:
            os.rename(live_path, rotated)
            with open(rotated, "r") as fh:
                existing = fh.read()
            with open(rotated, "w") as fh:
                fh.write(header_line)
                fh.write(existing)
            with open(live_path, "w"):
                pass  # truncate to empty live file
            logger.info(
                "rotate_event_streams: %s → %s (cycle=%d reason=%s)",
                os.path.basename(live_path), os.path.basename(rotated), cycle_n, reason,
            )
        except OSError as exc:
            logger.warning(
                "rotate_event_streams: failed to rotate %s (cycle=%d): %s",
                live_path, cycle_n, exc,
            )

    _rotate_one(live_events, "orchestration-events")
    _rotate_one(live_state_events, "orchestration-state-events")

    return cycle_n


def _rotate_plan_and_digest_for_new_lineage(
    project_path: str, new_lineage_id: str,
) -> Optional[str]:
    """Section 4b.1/4b.2: rename live plan + digest when starting on a new lineage.

    Called from the sentinel-start path BEFORE the new lineage's plan is
    written or its digest is decomposed.  When the on-disk live plan
    file's `input_path` (canonicalised) differs from `new_lineage_id`,
    the live plan + domains + digest dir get a
    `-<old-slug>` sibling rename so the lineage-aware reader can find
    them later.

    Returns the slug used for the rename, or None when no rotation
    happened (first sentinel ever, or same-lineage restart).
    """
    from .paths import LineagePaths
    from .types import canonicalise_spec_path, slug as _slug

    lp_live = LineagePaths(project_path)
    orch = lp_live.orchestration_dir
    live_plan = lp_live.plan_file
    if not os.path.isfile(live_plan):
        return None

    try:
        with open(live_plan) as fh:
            plan = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("rotate_plan: cannot read %s: %s", live_plan, exc)
        return None

    old_input = plan.get("input_path") or ""
    if not old_input:
        return None
    try:
        old_lineage = canonicalise_spec_path(old_input, project_path)
    except (ValueError, OSError):
        return None
    if old_lineage == new_lineage_id:
        return None

    # Use LineagePaths bound to the OLD lineage to derive the slugged
    # destination paths — keeps every literal inside the resolver.
    lp_old = LineagePaths(project_path, lineage_id=old_lineage)
    old_slug = lp_old.slug or _slug(old_lineage)
    rename_pairs = [
        (live_plan, lp_old.slugged_path(kind="plan_file")),
        (lp_live.plan_domains_file, lp_old.slugged_path(kind="plan_domains_file")),
    ]
    for src, dst in rename_pairs:
        if os.path.exists(src):
            try:
                if os.path.exists(dst):
                    logger.warning(
                        "rotate_plan: target %s exists, removing before rename", dst,
                    )
                    if os.path.isdir(dst):
                        import shutil
                        shutil.rmtree(dst)
                    else:
                        os.remove(dst)
                os.rename(src, dst)
                logger.info("rotate_plan: %s → %s", src, dst)
            except OSError as exc:
                logger.warning("rotate_plan: rename %s → %s failed: %s", src, dst, exc)

    # Digest dir lives under the project tree.  LineagePaths owns the
    # canonical location; we resolve via lp_live (digest_dir) for the
    # source and lp_old.slugged_path() for the destination.
    digest_live = lp_live.digest_dir
    digest_rotated = lp_old.slugged_path(kind="digest_dir")
    if os.path.isdir(digest_live):
        try:
            if os.path.exists(digest_rotated):
                import shutil
                shutil.rmtree(digest_rotated)
            os.rename(digest_live, digest_rotated)
            logger.info("rotate_plan: %s → %s", digest_live, digest_rotated)
        except OSError as exc:
            logger.warning(
                "rotate_plan: digest rename %s → %s failed: %s",
                digest_live, digest_rotated, exc,
            )

    return old_slug


def _claude_mangle_path(path: str) -> str:
    """Mangle a worktree path the same way Claude CLI does for ~/.claude/projects/."""
    return path.lstrip("/").replace("/", "-").replace(".", "-").replace("_", "-")


def _compute_session_summary(worktree_path: Optional[str]) -> dict:
    """Aggregate Claude-session metrics for a worktree about to be archived.

    Section 2.1 of run-history-and-phase-continuity.  Reads every
    `~/.claude/projects/-<mangled-worktree>/*.jsonl` file (Claude's own
    session storage) and returns the summary block defined in the spec.

    Missing worktree path or missing session dir produces a zero-valued
    summary with null timestamps — never raises.
    """
    summary = {
        "call_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_create_tokens": 0,
        "first_call_ts": None,
        "last_call_ts": None,
        "total_duration_ms": 0,
    }
    if not worktree_path:
        return summary
    sessions_dir = (
        os.path.expanduser("~/.claude/projects/-")
        + _claude_mangle_path(worktree_path)
    )
    if not os.path.isdir(sessions_dir):
        logger.debug(
            "compute_session_summary: no session dir at %s", sessions_dir,
        )
        return summary

    first_ts: Optional[str] = None
    last_ts: Optional[str] = None
    for entry_name in os.listdir(sessions_dir):
        if not entry_name.endswith(".jsonl"):
            continue
        path = os.path.join(sessions_dir, entry_name)
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("type") != "assistant":
                        continue
                    summary["call_count"] += 1
                    msg = entry.get("message") or {}
                    usage = msg.get("usage") or {}
                    summary["input_tokens"] += int(usage.get("input_tokens", 0) or 0)
                    summary["output_tokens"] += int(usage.get("output_tokens", 0) or 0)
                    summary["cache_read_tokens"] += int(
                        usage.get("cache_read_input_tokens", 0) or 0
                    )
                    summary["cache_create_tokens"] += int(
                        usage.get("cache_creation_input_tokens", 0) or 0
                    )
                    ts = entry.get("timestamp") or msg.get("created_at") or ""
                    if ts:
                        if first_ts is None or ts < first_ts:
                            first_ts = ts
                        if last_ts is None or ts > last_ts:
                            last_ts = ts
        except OSError as exc:
            logger.debug(
                "compute_session_summary: cannot read %s: %s", path, exc,
            )
            continue

    summary["first_call_ts"] = first_ts
    summary["last_call_ts"] = last_ts
    if first_ts and last_ts:
        try:
            from datetime import datetime as _dt
            t0 = _dt.fromisoformat(first_ts.replace("Z", "+00:00"))
            t1 = _dt.fromisoformat(last_ts.replace("Z", "+00:00"))
            summary["total_duration_ms"] = max(
                int((t1 - t0).total_seconds() * 1000), 0
            )
        except (TypeError, ValueError):
            summary["total_duration_ms"] = 0
    return summary


def _archive_completed_to_jsonl(state_file: str) -> None:
    """Archive completed-change records before replan.

    Each line is a flat JSON object keyed by change name. Fields mirror the
    live-state dict enough that the UI can group archived entries by phase and
    sum tokens alongside active changes.
    """
    from .paths import LineagePaths
    state = load_state(state_file)
    archive_path = LineagePaths.from_state_file(state_file).state_archive

    completed = [
        c for c in state.changes
        if c.status in ("merged", "done", "failed", "merge-blocked", "skipped", "integration-failed")
    ]
    if not completed:
        return

    existing: set[str] = set()
    if os.path.exists(archive_path):
        try:
            with open(archive_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        existing.add(json.loads(line).get("name", ""))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass

    new_completed = [c for c in completed if c.name not in existing]
    if not new_completed:
        return

    try:
        with open(archive_path, "a") as f:
            for c in new_completed:
                # Section 13.2 / AC-32: every archive entry is tagged with
                # the lineage + session id sourced from the change (which
                # inherited it from state at init/replan time).  The state's
                # value is the fallback for changes minted before this
                # change landed, so historic re-archives still get a tag.
                entry = {
                    "name": c.name,
                    "status": c.status,
                    "phase": c.phase,
                    "complexity": c.complexity,
                    "change_type": c.change_type,
                    "depends_on": c.depends_on,
                    "scope": c.scope,
                    "tokens_used": c.tokens_used,
                    "input_tokens": c.input_tokens,
                    "output_tokens": c.output_tokens,
                    "cache_read_tokens": c.cache_read_tokens,
                    "cache_create_tokens": c.cache_create_tokens,
                    "started_at": c.started_at,
                    "completed_at": c.completed_at,
                    "worktree_path": c.worktree_path,
                    "plan_version": state.plan_version,
                    "archived_at": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
                    "spec_lineage_id": c.spec_lineage_id or state.spec_lineage_id,
                    "sentinel_session_id": c.sentinel_session_id or state.sentinel_session_id,
                    "sentinel_session_started_at": (
                        c.sentinel_session_started_at or state.sentinel_session_started_at
                    ),
                    # Section 2.2 — embed Claude session aggregates so the
                    # Tokens / LLM-calls APIs can render this change after
                    # the worktree has been cleaned up.
                    "session_summary": _compute_session_summary(c.worktree_path),
                    # Preserve gate summary fields so the Changes tab's Gates
                    # column + the per-row DAG stay populated after the live
                    # entry is dropped from state.json on replan.  Timings +
                    # attempt counters round out the picture for learnings.
                    "build_result": c.build_result,
                    "test_result": c.test_result,
                    "e2e_result": c.e2e_result,
                    "review_result": c.review_result,
                    "smoke_result": c.smoke_result,
                    "spec_coverage_result": c.spec_coverage_result,
                    "gate_build_ms": c.gate_build_ms,
                    "gate_test_ms": c.gate_test_ms,
                    "gate_e2e_ms": c.gate_e2e_ms,
                    "gate_review_ms": c.gate_review_ms,
                    "gate_verify_ms": c.gate_verify_ms,
                    "gate_total_ms": c.gate_total_ms,
                    "verify_retry_count": c.verify_retry_count,
                    "redispatch_count": c.redispatch_count,
                }
                f.write(json.dumps(entry) + "\n")
        logger.info("Archived %d completed changes to %s", len(new_completed), archive_path)
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
        from .paths import LineagePaths
        # Resolve digest_dir via the lineage-aware resolver so non-live
        # lineages pick up `digest-<slug>/` and the live one picks up the
        # canonical project-local digest tree.
        _project_dir = os.path.dirname(state_file) or os.getcwd()
        logger.debug("Dispatch: project_dir=%s (from state_file=%s)", _project_dir, state_file)
        try:
            _digest_dir = LineagePaths.from_state_file(
                state_file, project_path=_project_dir,
            ).digest_dir
        except Exception:
            _digest_dir = ""
        if not os.path.isdir(_digest_dir):
            _digest_dir = ""
        if not _digest_dir:
            logger.warning(
                "digest_dir is empty for dispatch — agents won't get Required Tests section"
            )
        logger.debug("Dispatch: digest_dir=%s, exists=%s", _digest_dir, os.path.isdir(_digest_dir) if _digest_dir else False)
        dispatch_ready_changes(
            state_file, d.max_parallel,
            default_model=d.default_model,
            model_routing=d.model_routing,
            team_mode=d.team_mode,
            context_pruning=d.context_pruning,
            event_bus=event_bus,
            digest_dir=_digest_dir,
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
                # No active blockers — recover.
                merge_retry = change.extras.get("merge_retry_count", 0)
                old_ff = change.extras.get("ff_retry_count", 0)
                # Only reset ff_retry if an issue was actually resolved (meaning something changed).
                # If no issues existed at all, the ff failure cause hasn't changed — don't retry.
                if change_issues:
                    # Issue was resolved — give fresh ff attempts
                    if old_ff:
                        update_change_field(state_file, change.name, "ff_retry_count", 0, event_bus=event_bus)
                    update_change_field(state_file, change.name, "merge_retry_count", merge_retry + 1, event_bus=event_bus)
                    update_change_field(state_file, change.name, "status", "done", event_bus=event_bus)
                    logger.info(
                        "Recovered merge-blocked %s — blocking issues resolved (ff_retry_count %d→0, merge_retry_count %d→%d)",
                        change.name, old_ff, merge_retry, merge_retry + 1,
                    )
                else:
                    # No issues existed — ff failure is structural (worktree gone, branch conflict).
                    # Don't reset ff_retry, just mark integration-failed to stop the loop.
                    logger.warning(
                        "merge-blocked %s has no active issues and ff_retry exhausted — marking integration-failed",
                        change.name,
                    )
                    update_change_field(state_file, change.name, "status", "integration-failed", event_bus=event_bus)
                    if event_bus:
                        event_bus.emit("CHANGE_INTEGRATION_FAILED", change=change.name,
                                       data={"reason": "ff_exhausted_no_issue"})
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
        (c.status in terminal_statuses
         # "merged" with step != done means post-merge work still running
         and not (c.status == "merged" and c.current_step not in ("done", None)))
        or (c.status == "pending" and deps_failed(state, c.name))
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

        # Regenerate the spec coverage report (LineagePaths.coverage_report) with live statuses
        try:
            from .planner import generate_coverage_report
            import json as _json
            # Use absolute paths based on state_file location
            _project_dir = os.path.dirname(os.path.abspath(state_file))
            from .paths import LineagePaths as _LP_tc
            _lp_tc = _LP_tc.from_state_file(state_file, project_path=_project_dir)
            plan_path = _lp_tc.plan_file
            plan_data = {}
            if os.path.isfile(plan_path):
                plan_data = _json.loads(open(plan_path).read())
            # Prefer state_file-relative resolution over SetRuntime (which uses cwd)
            _default_digest = _lp_tc.digest_dir
            _default_coverage = _lp_tc.coverage_report
            if not os.path.isdir(_default_digest):
                try:
                    from .paths import SetRuntime
                    _rt = SetRuntime()
                    if os.path.isdir(_rt.digest_dir):
                        logger.warning("digest_dir: state-relative %s missing, falling back to SetRuntime %s", _default_digest, _rt.digest_dir)
                        _default_digest = _rt.digest_dir
                        _default_coverage = _rt.spec_coverage_report
                except Exception:
                    pass
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
        from .paths import LineagePaths as _LP_hr
        project_dir = os.path.dirname(state_file)
        _lp_hr = _LP_hr.from_state_file(state_file, project_path=project_dir)
        plan_path = _lp_hr.plan_file
        digest_dir = _lp_hr.digest_dir
        generate_report(
            state_path=state_file,
            plan_path=plan_path,
            digest_dir=digest_dir,
        )
    except Exception as _e:
        logger.debug("HTML report generation failed: %s", _e)


def _generate_review_findings_summary_safe(state_file: str) -> None:
    """Generate review findings summary from JSONL log (exception-safe)."""
    try:
        from .verifier import generate_review_findings_summary
        from .paths import LineagePaths as _LP_rf
        _project_dir = os.path.dirname(state_file)
        _lp_rf = _LP_rf.from_state_file(state_file, project_path=_project_dir)
        findings_path = _lp_rf.review_findings
        summary_path = os.path.join(
            os.path.dirname(findings_path), "review-findings-summary.md"
        )
        result = generate_review_findings_summary(findings_path, summary_path)
        if result:
            logger.info("Review findings summary: %s", result)
    except Exception as _e:
        logger.debug("Review findings summary failed: %s", _e)


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

        from .paths import LineagePaths as _LP_pr
        _project_dir = os.path.dirname(state_file)
        _lp_pr = _LP_pr.from_state_file(state_file, project_path=_project_dir)
        findings_path = _lp_pr.review_findings
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
