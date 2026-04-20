"""Trigger orchestration: dedup, retry budgets, rate limits, dispatch.

The daemon hands a list of `AnomalyTrigger` objects to `TriggerExecutor`
each poll cycle. The executor:

  1. Drops triggers whose retry budget is exhausted (per type+change pair)
  2. Drops triggers when the global hourly rate limit is hit
  3. Spawns ONE ephemeral Claude per remaining trigger, sequentially
  4. Records every spawn (and every skip) as a SUPERVISOR_TRIGGER event
  5. Updates `SupervisorStatus` counters in place (daemon persists)

Sequential dispatch is intentional: two ephemeral Claudes running against
the same project at once would race on the inbox/finding/git state and
likely corrupt each other's work. For a poll cycle that fires N triggers,
the executor drains them in priority order until budgets are exhausted.

The executor mutates `SupervisorStatus.trigger_attempts`,
`ephemeral_spawns_ts`, and `trigger_counters` directly. Persistence is
the daemon's responsibility — the executor stays I/O-only on the events
log and the spawn subprocess.
"""

from __future__ import annotations

import hashlib
import re
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from .anomaly import AnomalyTrigger
from .ephemeral import EphemeralResult, spawn_ephemeral_claude
from .history import build_prior_attempts_summary
from .prompts import build_trigger_prompt
from .state import SupervisorStatus


# fix-replan-stuck-gate-and-decomposer section 5: exponential back-off steps
# applied per (trigger, change, reason_hash) tuple when a trigger hits
# retry_budget_exhausted. Each successive exhaustion advances to the next
# step; the value is capped at the last entry. Values in seconds.
BACKOFF_STEPS_SECONDS: tuple[int, ...] = (60, 120, 240, 480, 600)


_REASON_NUMERIC_RE = re.compile(r"(?<!\w)\d+(?:\.\d+)?")


def _normalize_reason(reason: str) -> str:
    """Strip variable numeric runs from a reason string.

    Detector reasons often embed a live counter (e.g. "orchestration.log
    silent for 605s" → "silent for 620s" → "silent for 635s"). Hashing
    the raw reason string makes every poll produce a different back-off
    tuple_key, defeating the suppression window (observed on
    craftbrew-run-20260421-0025 where the supervisor re-emitted
    `skipped: retry_budget_exhausted` every 15s because each poll had a
    new reason_hash). Normalize by collapsing all numeric literals to a
    sentinel `<N>` before hashing, so the stable part of the reason
    drives the tuple_key.
    """
    return _REASON_NUMERIC_RE.sub("<N>", reason or "")


def _reason_hash(reason: str) -> str:
    """Stable 12-char hex of a trigger's reason string.

    Used in the back-off tuple key so the same trigger+change but a
    different reason category (e.g. budget-exhausted vs rate-limited)
    gets its own back-off window. Variable numeric runs in the reason
    are collapsed to a sentinel first (see `_normalize_reason`).
    """
    return hashlib.sha1(
        _normalize_reason(reason).encode("utf-8", errors="replace"),
    ).hexdigest()[:12]


def _backoff_tuple_key(trig: AnomalyTrigger) -> str:
    """Build the canonical trigger_backoffs key: "{trigger}::{change}::{reason_hash}".

    `change` is "" for orchestration-scoped triggers (log_silence, etc.).
    """
    change = trig.change or ""
    return f"{trig.type}::{change}::{_reason_hash(trig.reason or '')}"

logger = logging.getLogger(__name__)


# Retry budgets per (trigger_type, change). Once a key reaches its budget,
# that (trigger, change) pair stops firing for the daemon's lifetime.
DEFAULT_RETRY_BUDGETS: dict[str, int] = {
    "process_crash": 3,
    "integration_failed": 3,
    "state_stall": 2,
    "token_stall": 2,
    "non_periodic_checkpoint": 5,
    "unknown_event_type": 1,
    "error_rate_spike": 2,
    "log_silence": 2,
    "terminal_state": 1,
}

# Global hourly cap on ephemeral Claude spawns. Protects against any
# detector bug that would otherwise loop-spawn Claude processes.
DEFAULT_GLOBAL_RATE_LIMIT_PER_HOUR = 20
RATE_LIMIT_WINDOW_SECONDS = 3600

# Trigger-specific model. Sonnet by default; opus for the high-stakes
# triggers per the design doc (integration_failed, terminal_state, and
# non_periodic_checkpoint).
DEFAULT_MODEL_BY_TRIGGER: dict[str, str] = {
    "integration_failed": "opus",
    "non_periodic_checkpoint": "opus",
    "terminal_state": "opus",
}


@dataclass
class TriggerOutcome:
    """Result of a single trigger dispatch attempt."""
    trigger: AnomalyTrigger
    skipped_reason: str = ""
    result: Optional[EphemeralResult] = None


class TriggerExecutor:
    """Stateful trigger dispatcher tied to a SupervisorStatus.

    Created once per daemon. Lives across poll cycles. Mutates the
    SupervisorStatus passed in but does NOT persist it — the daemon owns
    persistence.
    """

    def __init__(
        self,
        *,
        status: SupervisorStatus,
        project_path: Path,
        events_path: Path,
        spec: str,
        emit_event: Callable[[str, dict], None],
        spawn_fn: Callable[..., EphemeralResult] = spawn_ephemeral_claude,
        retry_budgets: dict[str, int] | None = None,
        rate_limit_per_hour: int = DEFAULT_GLOBAL_RATE_LIMIT_PER_HOUR,
        clock: Callable[[], float] = time.time,
    ):
        self.status = status
        self.project_path = project_path
        self.events_path = events_path
        self.spec = spec
        self.emit_event = emit_event
        self.spawn_fn = spawn_fn
        self.retry_budgets = retry_budgets or DEFAULT_RETRY_BUDGETS
        self.rate_limit_per_hour = rate_limit_per_hour
        self.clock = clock

    # ── Public entry point ──────────────────────────────

    def execute(self, triggers: list[AnomalyTrigger]) -> list[TriggerOutcome]:
        """Run the given triggers in priority order. Returns one outcome per."""
        # Clear back-off entries for tuples whose detector's condition is no
        # longer firing this poll — otherwise a transient stall that later
        # recovers would keep suppressing a fresh occurrence far into the
        # future. (Section 5 task 5.4: "clear when is_triggered() returns
        # False on a subsequent poll".)
        active_keys = {_backoff_tuple_key(t) for t in triggers}
        to_clear = [k for k in list(self.status.trigger_backoffs.keys())
                    if k not in active_keys]
        for k in to_clear:
            del self.status.trigger_backoffs[k]

        outcomes: list[TriggerOutcome] = []
        for trig in sorted(triggers, key=lambda t: t.priority):
            outcome = self._execute_one(trig)
            outcomes.append(outcome)
            # After a terminal_state trigger has actually been dispatched,
            # the daemon will exit on the next poll — no point continuing.
            if trig.type == "terminal_state" and outcome.result is not None:
                break
        return outcomes

    # ── budget + rate limit ──────────────────────────────

    def _budget_key(self, trig: AnomalyTrigger) -> str:
        return f"{trig.type}:{trig.change}" if trig.change else trig.type

    def _budget_exhausted(self, trig: AnomalyTrigger) -> bool:
        budget = self.retry_budgets.get(trig.type, 1)
        used = self.status.trigger_attempts.get(self._budget_key(trig), 0)
        return used >= budget

    def _rate_limit_hit(self) -> bool:
        cutoff = self.clock() - RATE_LIMIT_WINDOW_SECONDS
        recent = [t for t in self.status.ephemeral_spawns_ts if t >= cutoff]
        # Prune in place — the status will be persisted by the daemon
        self.status.ephemeral_spawns_ts = recent
        return len(recent) >= self.rate_limit_per_hour

    # ── dispatch ─────────────────────────────────────────

    def _execute_one(self, trig: AnomalyTrigger) -> TriggerOutcome:
        # Section 5 task 5.2: back-off window. If the tuple is currently
        # suppressed, SKIP emission entirely (no SUPERVISOR_TRIGGER event
        # written, no Claude spawn). We still return a TriggerOutcome so
        # the caller can observe the skip if needed.
        tuple_key = _backoff_tuple_key(trig)
        now = self.clock()
        backoff_entry = self.status.trigger_backoffs.get(tuple_key)
        if backoff_entry:
            back_off_until = float(backoff_entry.get("back_off_until", 0) or 0)
            if now < back_off_until:
                logger.debug(
                    "[supervisor] trigger %s suppressed by back-off (key=%s, "
                    "step=%s, %.1fs remaining)",
                    trig.type, tuple_key,
                    backoff_entry.get("step"),
                    back_off_until - now,
                )
                return TriggerOutcome(
                    trigger=trig,
                    skipped_reason="back_off_active",
                )

        if self._budget_exhausted(trig):
            # Section 5 task 5.3: advance the back-off step on each repeat
            # exhaustion. Step 0 → 60s, 1 → 120s, …, cap at 600s.
            prior_step = int(backoff_entry.get("step", 0)) if backoff_entry else 0
            next_step = min(prior_step + 1, len(BACKOFF_STEPS_SECONDS))
            window = BACKOFF_STEPS_SECONDS[min(next_step - 1, len(BACKOFF_STEPS_SECONDS) - 1)]
            self.status.trigger_backoffs[tuple_key] = {
                "step": next_step,
                "back_off_until": now + window,
            }
            logger.info(
                "[supervisor] trigger %s retry_budget_exhausted → back-off "
                "step=%d window=%ds (key=%s)",
                trig.type, next_step, window, tuple_key,
            )
            self._record_skip(trig, "retry_budget_exhausted")
            return TriggerOutcome(trigger=trig, skipped_reason="retry_budget_exhausted")
        if self._rate_limit_hit():
            self._record_skip(trig, "rate_limit_hit")
            return TriggerOutcome(trigger=trig, skipped_reason="rate_limit_hit")

        # Mark attempt + spawn time BEFORE invoking Claude so a buggy
        # detector that fires every poll can't spawn-flood.
        key = self._budget_key(trig)
        self.status.trigger_attempts[key] = self.status.trigger_attempts.get(key, 0) + 1
        self.status.ephemeral_spawns_ts.append(self.clock())
        self.status.trigger_counters[trig.type] = (
            self.status.trigger_counters.get(trig.type, 0) + 1
        )

        prior = build_prior_attempts_summary(
            self.events_path,
            trigger=trig.type,
            change=trig.change,
        )
        prompt = build_trigger_prompt(
            trigger=trig.type,
            reason=trig.reason,
            change=trig.change,
            context=trig.context,
            project_path=str(self.project_path),
            spec=self.spec,
            prior_attempts_summary=prior,
        )
        model = DEFAULT_MODEL_BY_TRIGGER.get(trig.type, "sonnet")
        attempt = self.status.trigger_attempts[key]

        logger.info(
            "[supervisor] Dispatching trigger %s change=%s model=%s attempt=%d/%d",
            trig.type, trig.change, model, attempt,
            self.retry_budgets.get(trig.type, 1),
        )

        result = self.spawn_fn(
            trigger=trig.type,
            prompt=prompt.full,
            cwd=str(self.project_path),
            project_path=str(self.project_path),
            model=model,
        )

        self._emit_trigger_event(trig, result)
        return TriggerOutcome(trigger=trig, result=result)

    # ── event emission ───────────────────────────────────

    def _emit_trigger_event(self, trig: AnomalyTrigger, result: EphemeralResult) -> None:
        self.emit_event("SUPERVISOR_TRIGGER", {
            "trigger": trig.type,
            "change": trig.change,
            "reason": trig.reason,
            "priority": trig.priority,
            "exit_code": result.exit_code,
            "timed_out": result.timed_out,
            "elapsed_ms": result.elapsed_ms,
            "stdout_tail": result.stdout_tail[-1024:],
            "attempt": self.status.trigger_attempts.get(self._budget_key(trig), 1),
        })

    def _record_skip(self, trig: AnomalyTrigger, reason: str) -> None:
        logger.info(
            "[supervisor] Skipping trigger %s change=%s — %s",
            trig.type, trig.change, reason,
        )
        self.emit_event("SUPERVISOR_TRIGGER", {
            "trigger": trig.type,
            "change": trig.change,
            "reason": trig.reason,
            "skipped": reason,
        })
