"""Periodic canary check — broad LLM oversight, ~every 15 minutes.

The canary is the safety net for failure modes the trigger detectors
miss. It runs on a fixed cadence regardless of activity, asks an
ephemeral Claude to look at a structured snapshot of orchestration
progress, and parses a single VERDICT line out of the reply.

Verdict format: the Claude must end its reply with one of:
    CANARY_VERDICT: ok | note | warn | stop

The runner acts on the verdict:
    ok    → log only
    note  → log to events with the observation
    warn  → escalate via finding (rate-limited per signature, 30 min)
    stop  → request orchestrator halt for user decision

Fail-safe: missing or unrecognised verdict → "note" (log and continue).
We never escalate on parse ambiguity.
"""

from __future__ import annotations

import datetime
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .ephemeral import EphemeralResult, spawn_ephemeral_claude
from .state import SupervisorStatus

logger = logging.getLogger(__name__)


DEFAULT_CANARY_INTERVAL_SECONDS = 900    # 15 min
WARN_RATE_LIMIT_SECONDS = 1800           # 30 min per pattern signature

VERDICT_RE = re.compile(
    r"CANARY_VERDICT\s*:\s*(ok|note|warn|stop)", re.IGNORECASE,
)


# ── Data classes ─────────────────────────────────────────


@dataclass
class CanaryDiff:
    """Structured snapshot of what's changed since the last canary."""
    poll_cycle: int
    window_start_iso: str
    window_end_iso: str
    merged_changes: list[str] = field(default_factory=list)
    running_changes: list[dict] = field(default_factory=list)
    pending_changes: list[str] = field(default_factory=list)
    failed_changes: list[str] = field(default_factory=list)
    event_summary: dict[str, int] = field(default_factory=dict)
    new_event_types: list[str] = field(default_factory=list)
    log_warns: int = 0
    log_errors: int = 0
    gate_ms: dict[str, int] = field(default_factory=dict)

    def render(self) -> str:
        lines = [
            f"## Canary check @ {self.window_end_iso} (poll cycle {self.poll_cycle})",
            "",
            f"### Window: {self.window_start_iso} → {self.window_end_iso}",
        ]
        if self.merged_changes:
            lines.append(f"- Merged: {', '.join(self.merged_changes)}")
        if self.running_changes:
            running_strs = [
                f"{c.get('name', '?')} (status={c.get('status', '?')}, "
                f"tokens={c.get('tokens_used', 0)}, retries={c.get('retries', 0)})"
                for c in self.running_changes
            ]
            lines.append(f"- Running: {', '.join(running_strs)}")
        if self.pending_changes:
            lines.append(f"- Pending: {', '.join(self.pending_changes)}")
        if self.failed_changes:
            lines.append(f"- Failed: {', '.join(self.failed_changes)}")
        lines.append("")
        if self.event_summary:
            top = sorted(self.event_summary.items(), key=lambda kv: -kv[1])[:8]
            lines.append("### Events (top 8):")
            for et, n in top:
                lines.append(f"  - {et}: {n}")
            lines.append("")
        lines.append(
            f"### Log severity in window: {self.log_warns} WARN, {self.log_errors} ERROR"
        )
        if self.new_event_types:
            lines.append(f"### New event types: {', '.join(self.new_event_types)}")
        if self.gate_ms:
            gate_str = ", ".join(f"{k}={v}ms" for k, v in self.gate_ms.items())
            lines.append(f"### Gate timings (avg): {gate_str}")
        lines.append("")
        lines.append(
            "### Question: does anything in the diff above warrant escalation?\n"
            "Reply with a short paragraph and end with exactly one of:\n"
            "    CANARY_VERDICT: ok\n"
            "    CANARY_VERDICT: note\n"
            "    CANARY_VERDICT: warn\n"
            "    CANARY_VERDICT: stop"
        )
        return "\n".join(lines)


@dataclass
class CanaryRun:
    """Result of one canary execution."""
    diff: CanaryDiff
    verdict: str
    raw_reply_tail: str
    elapsed_ms: int
    exit_code: int
    timed_out: bool


# ── Public helpers ───────────────────────────────────────


def parse_canary_verdict(text: str) -> str:
    """Extract the verdict from a Claude reply.

    Fail-safe: missing or unrecognised verdict → "note" (log only).
    """
    if not text:
        return "note"
    match = VERDICT_RE.search(text)
    if not match:
        return "note"
    return match.group(1).lower()


def build_canary_diff(
    *,
    state: dict | None,
    new_events: list[dict],
    poll_cycle: int,
    window_start_iso: str,
    window_end_iso: str,
    log_warns: int = 0,
    log_errors: int = 0,
    new_event_types: list[str] | None = None,
) -> CanaryDiff:
    """Build the structured diff for one canary check from raw inputs."""
    diff = CanaryDiff(
        poll_cycle=poll_cycle,
        window_start_iso=window_start_iso,
        window_end_iso=window_end_iso,
        log_warns=log_warns,
        log_errors=log_errors,
        new_event_types=list(new_event_types or []),
    )

    if state:
        for change in state.get("changes") or []:
            name = str(change.get("name", ""))
            status = (change.get("status") or "").lower()
            if status in ("merged", "skipped", "skip_merged"):
                diff.merged_changes.append(name)
            elif status == "failed" or "failed" in status:
                diff.failed_changes.append(name)
            elif status in ("pending", "dep-blocked"):
                diff.pending_changes.append(name)
            else:
                diff.running_changes.append({
                    "name": name,
                    "status": status,
                    "tokens_used": int(change.get("tokens_used", 0) or 0),
                    "retries": int(change.get("redispatch_count", 0) or 0),
                })

    # Aggregate event counts (skip noisy heartbeats)
    for ev in new_events:
        et = ev.get("type")
        if not et or et == "WATCHDOG_HEARTBEAT":
            continue
        diff.event_summary[et] = diff.event_summary.get(et, 0) + 1

    # Average gate timings across the changes
    if state:
        gate_totals: dict[str, list[int]] = {}
        for change in state.get("changes") or []:
            for key in ("gate_build_ms", "gate_test_ms", "gate_e2e_ms", "gate_review_ms"):
                v = int(change.get(key, 0) or 0)
                if v > 0:
                    short = key.replace("gate_", "").replace("_ms", "")
                    gate_totals.setdefault(short, []).append(v)
        for k, vals in gate_totals.items():
            diff.gate_ms[k] = sum(vals) // len(vals)

    return diff


# ── Runner ───────────────────────────────────────────────


class CanaryRunner:
    """Stateful canary scheduler tied to a SupervisorStatus.

    Created once per daemon. The daemon's main loop checks `is_due()`
    every poll cycle and calls `run(diff)` when true. Mutates
    `SupervisorStatus.last_canary_at` and `canary_warn_log` in place.
    """

    def __init__(
        self,
        *,
        status: SupervisorStatus,
        project_path: Path,
        spec: str,
        emit_event: Callable[[str, dict], None],
        interval_seconds: int = DEFAULT_CANARY_INTERVAL_SECONDS,
        spawn_fn: Callable[..., EphemeralResult] = spawn_ephemeral_claude,
        clock: Callable[[], float] = time.time,
    ):
        self.status = status
        self.project_path = project_path
        self.spec = spec
        self.emit_event = emit_event
        self.interval = interval_seconds
        self.spawn_fn = spawn_fn
        self.clock = clock

    def is_due(self) -> bool:
        last = self._last_canary_epoch()
        if last <= 0:
            return True  # never run
        return (self.clock() - last) >= self.interval

    def run(self, diff: CanaryDiff) -> CanaryRun:
        """Spawn the canary Claude and parse its verdict."""
        prompt = self._build_prompt(diff)
        result = self.spawn_fn(
            trigger="canary",
            prompt=prompt,
            cwd=str(self.project_path),
            project_path=str(self.project_path),
            model="sonnet",
            timeout=600,
            max_turns=15,
        )
        verdict = parse_canary_verdict(result.stdout_tail)

        # Always update last_canary_at, even on failure — failure to
        # parse a verdict is still a "we tried" and we don't want to
        # immediately retry on the next poll.
        self.status.last_canary_at = (
            datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()
        )

        canary = CanaryRun(
            diff=diff,
            verdict=verdict,
            raw_reply_tail=result.stdout_tail[-1024:],
            elapsed_ms=result.elapsed_ms,
            exit_code=result.exit_code,
            timed_out=result.timed_out,
        )

        self._handle_verdict(canary)
        self._emit_event(canary)
        return canary

    # ── verdict handling ─────────────────────────────────

    def _handle_verdict(self, run: CanaryRun) -> None:
        v = run.verdict
        if v == "warn":
            sig = _signature(run.raw_reply_tail)
            if self._warn_rate_limited(sig):
                logger.info(
                    "[supervisor] Canary warn rate-limited (signature=%s)", sig,
                )
                run.verdict = "note"  # downgrade for the emitted event
                return
            self._record_warn(sig)
            logger.warning(
                "[supervisor] Canary WARN: %s", run.raw_reply_tail[:200],
            )
        elif v == "stop":
            logger.error(
                "[supervisor] Canary STOP: %s", run.raw_reply_tail[:200],
            )

    def _warn_rate_limited(self, signature: str) -> bool:
        last = self.status.canary_warn_log.get(signature, "")
        if not last:
            return False
        try:
            last_dt = datetime.datetime.fromisoformat(last)
        except ValueError:
            return False
        # Compare aware-to-aware. last_dt may be UTC or local-with-offset
        # (historical records), both carry tzinfo so subtraction works.
        now = datetime.datetime.now(datetime.timezone.utc)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=datetime.timezone.utc)
        delta = (now - last_dt).total_seconds()
        return delta < WARN_RATE_LIMIT_SECONDS

    def _record_warn(self, signature: str) -> None:
        self.status.canary_warn_log[signature] = (
            datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()
        )

    # ── helpers ──────────────────────────────────────────

    def _emit_event(self, run: CanaryRun) -> None:
        self.emit_event("CANARY_CHECK", {
            "verdict": run.verdict,
            "elapsed_ms": run.elapsed_ms,
            "exit_code": run.exit_code,
            "timed_out": run.timed_out,
            "merged": len(run.diff.merged_changes),
            "running": len(run.diff.running_changes),
            "pending": len(run.diff.pending_changes),
            "failed": len(run.diff.failed_changes),
            "warns": run.diff.log_warns,
            "errors": run.diff.log_errors,
            "tail": run.raw_reply_tail[-512:],
        })

    def _build_prompt(self, diff: CanaryDiff) -> str:
        return (
            "You are the set-supervisor's periodic canary. The Python "
            "daemon spawned you on a 15-minute schedule to look at a "
            "structured snapshot of orchestration progress and judge "
            "whether anything looks off.\n"
            "\n"
            "Be biased toward 'ok' or 'note'. Only escalate to 'warn' "
            "for real anomalies (stuck loops, repeated failures, token "
            "burn with no progress). Reserve 'stop' for catastrophic "
            "issues that require immediate human intervention.\n"
            "\n"
            f"{diff.render()}\n"
        )

    def _last_canary_epoch(self) -> float:
        if not self.status.last_canary_at:
            return 0.0
        try:
            dt = datetime.datetime.fromisoformat(self.status.last_canary_at)
            return dt.timestamp()
        except ValueError:
            return 0.0


# ── Helpers ──────────────────────────────────────────────


def _signature(text: str) -> str:
    """Compact signature for warn rate-limiting.

    Strips digits, lowercases, and keeps the first 64 chars. Two warns
    that differ only by token count or PID get the same signature.
    """
    if not text:
        return "(empty)"
    cleaned = re.sub(r"\d+", "N", text.lower()).strip()
    return cleaned[:64]
