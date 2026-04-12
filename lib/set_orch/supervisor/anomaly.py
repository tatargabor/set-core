"""Anomaly trigger detectors for the supervisor daemon (Phase 2).

Each detector inspects supervisor + orchestrator state and yields zero or
more `AnomalyTrigger` objects describing why an ephemeral Claude should
be invoked. Detectors are pure functions of an `AnomalyContext` — they
do NOT spawn processes, mutate persistent state, or read files outside
the context. The supervisor daemon's main loop dispatches the returned
triggers through `triggers.execute_triggers()`.

Trigger types (Phase 2):

  process_crash            — orchestrator PID is gone, status not terminal
  state_stall              — orchestration-state.json mtime unchanged > 5 min
  token_stall              — change tokens > 500k AND no state movement 30 min
  integration_failed       — change.status contains "integration" + "failed"
  non_periodic_checkpoint  — CHECKPOINT event with reason != "periodic"
  unknown_event_type       — first occurrence of an unrecognised event type
  error_rate_spike         — WARN/ERROR rate > 3× rolling baseline
  log_silence              — no new log lines in 5 min, process alive
  terminal_state           — status entered done/time_limit/stopped + dead

Adding a new trigger: append a `detect_*` function and call it from
`scan_for_anomalies`. Update KNOWN_EVENT_TYPES in this file when the
orchestrator gains a new event type so the unknown_event_type detector
stops false-firing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Module configuration ──────────────────────────────────

# Event types the orchestrator emits during normal operation. The
# unknown_event_type detector fires once for any event type NOT in this
# set (and not yet learned by the supervisor in `status.known_event_types`).
KNOWN_EVENT_TYPES: frozenset[str] = frozenset({
    # State + dispatcher
    "STATE_CHANGE", "DISPATCH", "CHANGE_DONE", "CHANGE_STALLED",
    "CHANGE_REDISPATCH", "CHANGE_RECONCILED", "CHANGE_RECOVERED",
    "CHANGE_INTEGRATION_FAILED", "STEP_TRANSITION", "REPLAN_DISPATCHED",
    "PHASE_ADVANCED", "CHANGE_SKIPPED",
    # Gates + verifier
    "GATE_START", "GATE_PASS", "GATE_SKIP_WARNING", "VERIFY_GATE",
    "INTEGRATION",
    # Merger
    "MERGE_ATTEMPT", "MERGE_START", "MERGE_PROGRESS",
    "MERGE_COMPLETE", "MERGE_SUCCESS",
    "CONFLICT_RESOLUTION_START", "CONFLICT_RESOLUTION_END",
    # Watchdog
    "WATCHDOG_HEARTBEAT", "WATCHDOG_REDISPATCH", "WATCHDOG_ESCALATION",
    "WATCHDOG_SALVAGE", "WATCHDOG_WARN",
    "IDLE_START", "IDLE_END",
    # Monitor loop
    "MONITOR_HEARTBEAT",
    # Per-iteration / Claude calls
    "ITERATION_END", "LLM_CALL", "CLASSIFIER_CALL",
    # Lifecycle
    "CHECKPOINT", "ERROR", "MANUAL_STOP", "MANUAL_RESUME",
    "WORKTREE_MISSING",
    "SHUTDOWN_STARTED", "SHUTDOWN_COMPLETE",
    "CHANGE_STOPPING", "CHANGE_STOPPED",
    # Pre-orchestration phase (bash scripts: digest.sh, orch-memory.sh, audit.sh)
    "DIGEST_STARTED", "DIGEST_COMPLETE", "DIGEST_FAILED",
    "MEMORY_HYGIENE",
    "AUDIT_CLEAN", "AUDIT_GAPS",
    "HOOK_BLOCKED",
    # Supervisor itself (we emit these)
    "SUPERVISOR_START", "SUPERVISOR_STOP", "SUPERVISOR_RESTART",
    "SUPERVISOR_INBOX", "SUPERVISOR_TRIGGER", "CANARY_CHECK",
})

# Status values that mean orchestration is finished — process death is
# expected, so the process_crash trigger should NOT fire.
TERMINAL_STATUSES: frozenset[str] = frozenset({
    "done", "time_limit", "stopped", "completed", "halted",
})

# Tunables (also overrideable per-run via the daemon, future work).
DEFAULT_STATE_STALL_SECS = 300        # 5 min
DEFAULT_LOG_SILENCE_SECS = 300        # 5 min
DEFAULT_TOKEN_STALL_LIMIT = 500_000   # tokens
DEFAULT_TOKEN_STALL_SECS = 1800       # 30 min
DEFAULT_ERROR_BASELINE_MULTIPLIER = 3
DEFAULT_ERROR_BASELINE_ALPHA = 0.3    # EMA smoothing factor
ERROR_BASELINE_MIN = 1.0              # don't trigger until baseline > this

LOG_SLICE_MAX_BYTES = 1_048_576       # never read more than 1 MB at a time


# ── Data classes ─────────────────────────────────────────


@dataclass
class AnomalyTrigger:
    """A single anomaly signal asking for an ephemeral Claude spawn.

    Fields:
        type:     trigger type (matches the detector name)
        change:   change name if change-scoped, else ""
        reason:   short human-readable description
        priority: lower number = higher priority. Used by triggers.py to
                  drain the queue when several fire on the same poll.
        context:  free-form dict the prompt builder can read
    """
    type: str
    change: str = ""
    reason: str = ""
    priority: int = 50
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnomalyContext:
    """All inputs an anomaly detector needs.

    Built once per poll cycle by the daemon and passed to scan_for_anomalies().
    Detectors may MUTATE the following mutable fields to publish state back
    to the daemon (which then persists them in supervisor.status.json):
        - known_event_types : set[str]
        - error_baseline    : dict
    Everything else is read-only by convention.
    """
    project_path: Path
    state_path: Optional[Path]
    events_path: Optional[Path]
    log_path: Optional[Path]
    state: Optional[dict]
    new_events: list[dict]
    orchestrator_pid: int
    orchestrator_alive: bool
    now: float                            # time.time()
    state_mtime: float                    # 0.0 if missing
    last_state_mtime: float
    last_state_change_at: float
    log_size: int
    last_log_size: int
    last_log_growth_at: float
    error_baseline: dict                  # mutable: detectors update it
    known_event_types: set[str]           # mutable: detectors learn from it


# ── Public entry point ───────────────────────────────────


def scan_for_anomalies(ctx: AnomalyContext) -> list[AnomalyTrigger]:
    """Run every detector against the context and return all firing triggers.

    Returned in priority order (lowest priority number first). The caller
    (triggers.TriggerExecutor) is responsible for retry budgets, rate
    limiting, and dispatch — this function only reports.
    """
    triggers: list[AnomalyTrigger] = []
    triggers.extend(detect_terminal_state(ctx))
    triggers.extend(detect_process_crash(ctx))
    triggers.extend(detect_integration_failed(ctx))
    triggers.extend(detect_non_periodic_checkpoint(ctx))
    triggers.extend(detect_state_stall(ctx))
    triggers.extend(detect_token_stall(ctx))
    triggers.extend(detect_unknown_event_type(ctx))
    triggers.extend(detect_error_rate_spike(ctx))
    triggers.extend(detect_log_silence(ctx))
    triggers.sort(key=lambda t: t.priority)
    return triggers


# ── Individual detectors ─────────────────────────────────


def detect_terminal_state(ctx: AnomalyContext) -> list[AnomalyTrigger]:
    """Orchestration entered a terminal status — emit final-report trigger.

    Fires once per poll when state.status is terminal AND the orchestrator
    process is dead. Highest priority — the daemon will exit shortly after,
    so this is the last useful trigger we can fire.
    """
    if not ctx.state:
        return []
    status = (ctx.state.get("status") or "").lower()
    if status not in TERMINAL_STATUSES:
        return []
    if ctx.orchestrator_alive:
        return []
    return [AnomalyTrigger(
        type="terminal_state",
        reason=f"state.status={status} and orchestrator pid={ctx.orchestrator_pid} dead",
        priority=1,
        context={"status": status, "pid": ctx.orchestrator_pid},
    )]


def detect_process_crash(ctx: AnomalyContext) -> list[AnomalyTrigger]:
    """Orchestrator PID gone but state.status is NOT terminal."""
    if ctx.orchestrator_alive or ctx.orchestrator_pid <= 0:
        return []
    if ctx.state:
        status = (ctx.state.get("status") or "").lower()
        if status in TERMINAL_STATUSES:
            return []
    return [AnomalyTrigger(
        type="process_crash",
        reason=f"orchestrator pid={ctx.orchestrator_pid} dead, status not terminal",
        priority=5,
        context={"pid": ctx.orchestrator_pid},
    )]


def detect_integration_failed(ctx: AnomalyContext) -> list[AnomalyTrigger]:
    """Any change in a `failed` terminal status — one trigger per change.

    Matches every status whose name contains ``failed``, including:
      - ``failed``                        (generic terminal failure after
                                           max_verify_retries exhausts)
      - ``integration-failed``            (legacy)
      - ``integration-e2e-failed``        (e2e gate exhausted)
      - ``integration-coverage-failed``   (coverage gate exhausted)

    The previous implementation required BOTH "integration" AND "failed"
    in the status, which missed the plain ``failed`` case. That case is
    the real terminal state the orchestrator uses when max_verify_retries
    is exhausted — so the supervisor was blind to the most common change
    failure mode on any run with non-trivial retry behavior. Caught
    mid-minishop-run-20260412-0103 on foundation-setup after 3 verify
    retries exhausted at 02:34; the trigger never fired.

    Note: ``skipped`` contains no "failed" substring and is excluded,
    correctly — skipped is an intentional no-op, not a failure.
    """
    if not ctx.state:
        return []
    out: list[AnomalyTrigger] = []
    for change in ctx.state.get("changes") or []:
        status = (change.get("status") or "").lower()
        if "failed" in status:
            out.append(AnomalyTrigger(
                type="integration_failed",
                change=str(change.get("name", "")),
                reason=f"change.status={status}",
                priority=10,
                context={
                    "status": status,
                    "tokens": int(change.get("tokens_used", 0) or 0),
                    "verify_retry_count": int(change.get("verify_retry_count", 0) or 0),
                },
            ))
    return out


def detect_non_periodic_checkpoint(ctx: AnomalyContext) -> list[AnomalyTrigger]:
    """CHECKPOINT events whose data.reason != "periodic".

    Periodic checkpoints are routine; non-periodic ones are a deliberate
    marker that something interesting happened (manual mark, replan,
    crash recovery point, etc.).
    """
    out: list[AnomalyTrigger] = []
    for ev in ctx.new_events:
        if ev.get("type") != "CHECKPOINT":
            continue
        reason = (ev.get("data") or {}).get("reason", "")
        if reason and reason != "periodic":
            out.append(AnomalyTrigger(
                type="non_periodic_checkpoint",
                reason=f"CHECKPOINT reason={reason}",
                priority=15,
                context={"checkpoint_reason": reason, "ts": ev.get("ts", "")},
            ))
    return out


def detect_state_stall(ctx: AnomalyContext) -> list[AnomalyTrigger]:
    """state.json mtime hasn't moved for > DEFAULT_STATE_STALL_SECS.

    Only fires when the orchestrator is alive AND state.status is
    "running". A stalled file on a finished run is not interesting.
    """
    if not ctx.orchestrator_alive or not ctx.state:
        return []
    status = (ctx.state.get("status") or "").lower()
    if status != "running":
        return []
    if ctx.state_mtime <= 0 or ctx.last_state_change_at <= 0:
        return []
    stall = ctx.now - ctx.last_state_change_at
    if stall < DEFAULT_STATE_STALL_SECS:
        return []
    return [AnomalyTrigger(
        type="state_stall",
        reason=f"state.json unchanged for {int(stall)}s (limit {DEFAULT_STATE_STALL_SECS}s)",
        priority=20,
        context={"stall_seconds": int(stall)},
    )]


def detect_token_stall(ctx: AnomalyContext) -> list[AnomalyTrigger]:
    """A change has burned > DEFAULT_TOKEN_STALL_LIMIT tokens with no movement.

    Heuristic: tokens above the limit AND status in {running, dispatched,
    fixing} AND state.json hasn't moved for > DEFAULT_TOKEN_STALL_SECS.
    The orchestrator does not record commit timestamps in the state file,
    so we approximate "no commit" with "no state movement". Phase 3 can
    upgrade this with a real git lookup.
    """
    if not ctx.state:
        return []
    out: list[AnomalyTrigger] = []
    stall = ctx.now - ctx.last_state_change_at if ctx.last_state_change_at else 0
    for change in ctx.state.get("changes") or []:
        tokens = int(change.get("tokens_used", 0) or 0)
        status = (change.get("status") or "").lower()
        if tokens < DEFAULT_TOKEN_STALL_LIMIT:
            continue
        if status not in ("running", "dispatched", "fixing"):
            continue
        if stall < DEFAULT_TOKEN_STALL_SECS:
            continue
        out.append(AnomalyTrigger(
            type="token_stall",
            change=str(change.get("name", "")),
            reason=f"tokens={tokens} and no state movement for {int(stall)}s",
            priority=25,
            context={"tokens": tokens, "stall_seconds": int(stall)},
        ))
    return out


def detect_unknown_event_type(ctx: AnomalyContext) -> list[AnomalyTrigger]:
    """First occurrence of an event type the supervisor has never seen.

    Once fired, the event type is added to `ctx.known_event_types` so the
    daemon can persist it (in `status.known_event_types`) and never
    re-fire for the same type.
    """
    out: list[AnomalyTrigger] = []
    for ev in ctx.new_events:
        et = ev.get("type")
        if not et or not isinstance(et, str):
            continue
        if et in KNOWN_EVENT_TYPES or et in ctx.known_event_types:
            continue
        out.append(AnomalyTrigger(
            type="unknown_event_type",
            reason=f"First occurrence of event type {et!r}",
            priority=40,
            context={"event_type": et, "first_seen_ts": ev.get("ts", "")},
        ))
        ctx.known_event_types.add(et)
    return out


def detect_error_rate_spike(ctx: AnomalyContext) -> list[AnomalyTrigger]:
    """WARN/ERROR lines in the new log slice > MULT × rolling baseline.

    The baseline is an exponential moving average over poll-cycle samples,
    stored in `ctx.error_baseline`. We don't trigger until the baseline is
    > ERROR_BASELINE_MIN to avoid early-run false positives where the
    first non-zero sample would otherwise look like an "infinite spike".
    """
    if not ctx.log_path or not ctx.log_path.is_file():
        return []
    if ctx.log_size <= ctx.last_log_size:
        # No new log content this poll → don't update baseline either
        return []
    new_warns, new_errors = _count_log_severity(
        ctx.log_path, ctx.last_log_size, ctx.log_size,
    )
    new_total = new_warns + new_errors
    baseline = float(ctx.error_baseline.get("avg_per_window", 0.0))
    new_baseline = (
        DEFAULT_ERROR_BASELINE_ALPHA * new_total
        + (1 - DEFAULT_ERROR_BASELINE_ALPHA) * baseline
    )
    ctx.error_baseline["avg_per_window"] = new_baseline
    ctx.error_baseline["last_window_count"] = new_total

    if baseline < ERROR_BASELINE_MIN:
        return []
    if new_total < DEFAULT_ERROR_BASELINE_MULTIPLIER * baseline:
        return []
    return [AnomalyTrigger(
        type="error_rate_spike",
        reason=(
            f"{new_total} WARN/ERROR lines in last poll, "
            f"baseline avg {baseline:.1f}"
        ),
        priority=30,
        context={
            "warn_count": new_warns,
            "error_count": new_errors,
            "baseline": round(baseline, 2),
        },
    )]


def detect_log_silence(ctx: AnomalyContext) -> list[AnomalyTrigger]:
    """No new log lines in DEFAULT_LOG_SILENCE_SECS but the process is alive."""
    if not ctx.orchestrator_alive:
        return []
    if not ctx.log_path or not ctx.log_path.is_file():
        return []
    if ctx.last_log_growth_at <= 0:
        return []
    if ctx.log_size > ctx.last_log_size:
        return []
    silence = ctx.now - ctx.last_log_growth_at
    if silence < DEFAULT_LOG_SILENCE_SECS:
        return []
    return [AnomalyTrigger(
        type="log_silence",
        reason=f"orchestration.log silent for {int(silence)}s",
        priority=35,
        context={"silence_seconds": int(silence)},
    )]


# ── Helpers ──────────────────────────────────────────────


def _count_log_severity(path: Path, start: int, end: int) -> tuple[int, int]:
    """Count WARN and ERROR markers in [start, end) of a log file.

    Bounded read: at most LOG_SLICE_MAX_BYTES per call to keep poll cycles
    cheap even when the log is huge.
    """
    if start < 0:
        start = 0
    span = end - start
    if span <= 0:
        return (0, 0)
    if span > LOG_SLICE_MAX_BYTES:
        span = LOG_SLICE_MAX_BYTES
        start = end - span
    try:
        with open(path, "rb") as f:
            f.seek(start)
            chunk = f.read(span)
    except OSError as exc:
        logger.warning("Could not read log slice for severity count: %s", exc)
        return (0, 0)
    text = chunk.decode("utf-8", errors="replace")
    warns = text.count(" WARNING") + text.count("[WARN]") + text.count(" WARN ")
    errors = text.count(" ERROR") + text.count("[ERROR]") + text.count(" CRITICAL")
    return (warns, errors)
