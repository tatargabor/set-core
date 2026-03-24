"""Gate pipeline runner — unified gate execution, retry, and batch state update.

Replaces the 600+ line copy-pasted gate logic in handle_change_done with a
composable pipeline that executes gates in order, handles skip/warn/block
semantics, and commits all results in a single locked_state write.

Functions:
    GateResult      — per-gate outcome dataclass
    GatePipeline    — orchestrates sequential gate execution
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import glob as glob_mod
import os
import shutil

from .state import Change, locked_state, update_change_field

logger = logging.getLogger(__name__)


# ─── Data Structures ──────────────────────────────────────────────


@dataclass
class GateResult:
    """Outcome of a single gate execution."""

    gate_name: str
    status: str  # "pass", "fail", "warn-fail", "skipped"
    output: str = ""
    duration_ms: int = 0
    stats: Optional[dict] = None
    # Retry context to inject when this gate triggers a retry
    retry_context: str = ""


# Type alias for gate executor functions
GateExecutor = Callable[..., GateResult]


@dataclass
class GateDefinition:
    """Declaration of a gate type — used by core and profile plugins.

    Universal gates are defined in verifier.py. Domain-specific gates
    are registered by profile plugins via register_gates().
    """

    name: str
    executor: GateExecutor
    position: str = "end"       # "start", "after:test", "before:review", "end"
    phase: str = "pre-merge"    # "pre-merge" or "post-merge"
    defaults: dict = field(default_factory=dict)
    # defaults: {change_type: mode} e.g. {"infrastructure": "skip", "feature": "run"}
    own_retry_counter: str = ""  # e.g. "build_fix_attempt_count"
    extra_retries: int = 0
    # Field mapping for commit_results (result_field, timing_field) or None for extras-only
    result_fields: Optional[tuple] = None  # e.g. ("build_result", "gate_build_ms")
    # Re-run in merge queue after integration? (fast gates only: build, test, e2e)
    run_on_integration: bool = False


def _resolve_gate_order(gates: list[GateDefinition]) -> list[GateDefinition]:
    """Merge universal + profile gates and sort by position hints.

    Position hints:
      "start"       — index 0
      "after:X"     — immediately after gate named X
      "before:X"    — immediately before gate named X
      "before:end"  — before the last gate
      "end"         — last position

    Algorithm: iteratively place gates whose dependencies are already placed.
    Gates with "start" go first, "end" goes last. Others are inserted relative
    to already-placed gates. Unresolvable gates append before end.
    """
    placed: list[GateDefinition] = []
    placed_names: set[str] = set()
    pending = list(gates)

    # Extract start and end gates first
    start_gates = [g for g in pending if g.position == "start"]
    end_gates = [g for g in pending if g.position == "end"]
    before_end_gates = [g for g in pending if g.position == "before:end"]
    pending = [g for g in pending if g.position not in ("start", "end", "before:end")]

    for g in start_gates:
        placed.append(g)
        placed_names.add(g.name)

    # Iteratively resolve — each pass places gates whose target is already placed
    max_passes = len(pending) + 1
    for _ in range(max_passes):
        still_pending = []
        progress = False
        for g in pending:
            pos = g.position
            if pos.startswith("after:"):
                target = pos[6:]
                if target in placed_names:
                    # Insert right after target (and any previously inserted after:target)
                    idx = max(i for i, p in enumerate(placed) if p.name == target) + 1
                    # Skip past any gates already inserted after this target
                    while idx < len(placed) and placed[idx].position == f"after:{target}":
                        idx += 1
                    placed.insert(idx, g)
                    placed_names.add(g.name)
                    progress = True
                else:
                    still_pending.append(g)
            elif pos.startswith("before:"):
                target = pos[7:]
                if target in placed_names:
                    idx = next(i for i, p in enumerate(placed) if p.name == target)
                    placed.insert(idx, g)
                    placed_names.add(g.name)
                    progress = True
                else:
                    still_pending.append(g)
            else:
                # No position hint — append in order
                placed.append(g)
                placed_names.add(g.name)
                progress = True
        pending = still_pending
        if not pending:
            break
        if not progress:
            # Unresolvable — append remaining before end
            break

    # Append any unresolved gates
    placed.extend(pending)
    placed.extend(before_end_gates)
    placed.extend(end_gates)
    return placed


# ─── Pipeline ─────────────────────────────────────────────────────


@dataclass
class _GateEntry:
    """Internal: a registered gate with its executor and options."""

    name: str
    executor: GateExecutor
    # If True, this gate uses its own retry counter (e.g. build_fix_attempt_count)
    # instead of the shared verify_retry_count.
    own_retry_counter: str = ""
    # Extra retries beyond max_retries (e.g. review gets +1)
    extra_retries: int = 0
    # Field mapping for commit_results: (result_field, timing_field) or None
    result_fields: Optional[tuple] = None


class GatePipeline:
    """Orchestrates sequential gate execution with unified retry/skip/warn logic.

    Usage:
        pipeline = GatePipeline(gc, state_file, change_name, max_retries=2)
        pipeline.register("build", build_executor)
        pipeline.register("test", test_executor)
        action = pipeline.run()
        # action is "continue" (all passed), "retry" (blocking fail, retries left),
        # or "failed" (blocking fail, retries exhausted)
        pipeline.commit_results()
    """

    def __init__(
        self,
        gc: Any,  # GateConfig
        state_file: str,
        change_name: str,
        change: Change,
        *,
        max_retries: int = 2,
        event_bus: Any = None,
    ) -> None:
        self.gc = gc
        self.state_file = state_file
        self.change_name = change_name
        self.change = change
        self.max_retries = max_retries
        self.event_bus = event_bus

        self._gates: list[_GateEntry] = []
        self.results: list[GateResult] = []
        self.stopped = False
        self.stop_action: str = ""  # "retry" or "failed"
        self.stop_gate: str = ""  # which gate caused the stop
        self._verify_retry_count = change.verify_retry_count

    def register(
        self,
        name: str,
        executor: GateExecutor,
        *,
        own_retry_counter: str = "",
        extra_retries: int = 0,
        result_fields: Optional[tuple] = None,
    ) -> None:
        """Register a gate to execute. Gates run in registration order."""
        self._gates.append(_GateEntry(
            name=name,
            executor=executor,
            own_retry_counter=own_retry_counter,
            extra_retries=extra_retries,
            result_fields=result_fields,
        ))

    def run(self) -> str:
        """Execute all registered gates in order.

        Returns:
            "continue" — all gates passed (or non-blocking failures)
            "retry"    — blocking failure, retry dispatched
            "failed"   — blocking failure, retries exhausted
        """
        for entry in self._gates:
            if self.stopped:
                break

            # Skip check
            if not self.gc.should_run(entry.name):
                self.results.append(GateResult(
                    gate_name=entry.name,
                    status="skipped",
                ))
                logger.info(
                    "Verify gate: %s SKIPPED for %s (gate_profile)",
                    entry.name, self.change_name,
                )
                continue

            # Execute
            start_ms = int(time.monotonic() * 1000)
            try:
                result = entry.executor()
            except Exception:
                logger.warning(
                    "Gate %s threw exception for %s",
                    entry.name, self.change_name, exc_info=True,
                )
                result = GateResult(
                    gate_name=entry.name,
                    status="fail",
                    output="gate executor threw exception",
                )
            elapsed_ms = int(time.monotonic() * 1000) - start_ms
            result.duration_ms = elapsed_ms
            result.gate_name = entry.name

            # Handle result
            if result.status == "pass":
                self.results.append(result)
                logger.info(
                    "Verify gate: %s passed for %s (%dms)",
                    entry.name, self.change_name, elapsed_ms,
                )

            elif result.status == "fail":
                if self.gc.is_blocking(entry.name):
                    self.results.append(result)
                    action = self._handle_blocking_failure(entry, result)
                    return action
                else:
                    # Non-blocking: convert to warn-fail
                    result.status = "warn-fail"
                    self.results.append(result)
                    logger.warning(
                        "Verify gate: %s failed for %s — non-blocking (gate=%s)",
                        entry.name, self.change_name, self.gc.get(entry.name, "?"),
                    )

            else:
                # "skipped", "warn-fail", or other — pass through
                self.results.append(result)

        return "continue"

    def _handle_blocking_failure(
        self, entry: _GateEntry, result: GateResult,
    ) -> str:
        """Handle a blocking gate failure: retry or fail.

        Returns "retry" or "failed".
        """
        self.stopped = True
        self.stop_gate = entry.name

        # Determine retry budget
        if entry.own_retry_counter:
            # Uses its own counter (e.g. build_fix_attempt_count)
            current_count = self.change.extras.get(entry.own_retry_counter, 0)
            limit = self.max_retries
        else:
            current_count = self._verify_retry_count
            limit = self.max_retries + entry.extra_retries

        if current_count < limit:
            # Retry available
            if entry.own_retry_counter:
                update_change_field(
                    self.state_file, self.change_name,
                    entry.own_retry_counter, current_count + 1,
                )
            else:
                self._verify_retry_count = current_count + 1
                update_change_field(
                    self.state_file, self.change_name,
                    "verify_retry_count", self._verify_retry_count,
                )

            update_change_field(
                self.state_file, self.change_name,
                "status", "verify-failed",
            )
            if result.retry_context:
                update_change_field(
                    self.state_file, self.change_name,
                    "retry_context", result.retry_context,
                )

            logger.error(
                "Verify gate: %s FAILED for %s — retrying (%d/%d)",
                entry.name, self.change_name,
                current_count + 1, limit,
            )
            self.stop_action = "retry"
            return "retry"
        else:
            # Retries exhausted
            update_change_field(
                self.state_file, self.change_name,
                "status", "failed",
            )
            logger.error(
                "Verify gate: %s FAILED for %s — retries exhausted (%d/%d)",
                entry.name, self.change_name,
                current_count, limit,
            )
            self.stop_action = "failed"
            return "failed"

    def commit_results(self) -> dict:
        """Write all gate results to state in a single locked_state block.

        Uses result_fields from _GateEntry (populated from GateDefinition)
        to map gate results to state fields. Gates without result_fields
        write to extras with generic naming.

        Returns a summary dict for event emission.
        """
        # Build field map from registered gate entries
        gate_field_map: dict[str, tuple[str, str]] = {}
        for entry in self._gates:
            if entry.result_fields:
                gate_field_map[entry.name] = entry.result_fields

        total_ms = 0
        summary: dict[str, Any] = {}

        with locked_state(self.state_file) as st:
            for c in st.changes:
                if c.name != self.change_name:
                    continue

                for r in self.results:
                    summary[r.gate_name] = r.status
                    total_ms += r.duration_ms

                    if r.gate_name in gate_field_map:
                        result_field, ms_field = gate_field_map[r.gate_name]
                        c.extras[result_field] = r.status
                        c.extras[ms_field] = r.duration_ms
                        # Also set dataclass fields where they exist
                        if hasattr(c, result_field):
                            setattr(c, result_field, r.status)
                        if hasattr(c, ms_field):
                            setattr(c, ms_field, r.duration_ms)
                    elif r.gate_name == "scope_check":
                        c.extras["scope_check"] = r.status
                    elif r.gate_name == "test_files":
                        c.extras["has_tests"] = r.status == "pass"
                    else:
                        # Generic fallback for profile-registered gates
                        c.extras[f"{r.gate_name}_result"] = r.status
                        if r.duration_ms:
                            c.extras[f"gate_{r.gate_name}_ms"] = r.duration_ms

                    # Store output for gates that produce useful output
                    if r.output and r.duration_ms > 0:
                        c.extras[f"{r.gate_name}_output"] = r.output[:2000]

                    # Store stats
                    if r.stats:
                        stats_field = f"{r.gate_name}_stats"
                        if hasattr(c, stats_field):
                            setattr(c, stats_field, r.stats)
                        else:
                            c.extras[stats_field] = r.stats

                c.extras["gate_total_ms"] = total_ms
                if hasattr(c, "gate_total_ms"):
                    c.gate_total_ms = total_ms

                # Update verify_retry_count from pipeline state
                c.verify_retry_count = self._verify_retry_count

                break

        summary["total_ms"] = total_ms
        summary["retries"] = self._verify_retry_count
        return summary


# ─── Unified Screenshot Collection ───────────────────────────────


def collect_screenshots(
    change_name: str,
    source_dir: str,
    category: str = "smoke",
    attempt: int | None = None,
    state_file: str = "",
) -> int:
    """Collect Playwright test-results screenshots to a consistent SetRuntime path.

    Args:
        change_name: Name of the change.
        source_dir: Directory containing test-results (e.g. "test-results" or worktree path).
        category: "smoke" or "e2e".
        attempt: Attempt number for smoke retries (None = no numbering).
        state_file: State file path (optional, for updating screenshot fields).

    Returns:
        Number of screenshot files collected.
    """
    if not os.path.isdir(source_dir):
        return 0

    # Resolve destination via SetRuntime, fall back to legacy path
    try:
        from .paths import SetRuntime
        rt = SetRuntime()
        if category == "smoke":
            base_dir = rt.smoke_screenshots_dir(change_name)
        else:
            base_dir = os.path.join(rt.screenshots_dir, category, change_name)
    except Exception:
        base_dir = f"set/orchestration/{category}-screenshots/{change_name}"

    if attempt is not None:
        dest_dir = os.path.join(base_dir, f"attempt-{attempt}")
    else:
        dest_dir = base_dir

    os.makedirs(dest_dir, exist_ok=True)

    # Copy screenshots
    if os.path.isdir(source_dir):
        try:
            shutil.copytree(source_dir, dest_dir, dirs_exist_ok=True)
        except Exception:
            logger.warning("Failed to copy screenshots from %s for %s", source_dir, change_name)

    # Count PNG files
    sc_count = len(glob_mod.glob(os.path.join(base_dir, "**", "*.png"), recursive=True))

    # Update state if provided
    if state_file:
        from .state import update_change_field as _ucf
        _ucf(state_file, change_name, f"{category}_screenshot_dir", base_dir)
        _ucf(state_file, change_name, f"{category}_screenshot_count", sc_count)

    logger.info(
        "Screenshots: collected %d %s images for %s%s",
        sc_count, category, change_name,
        f" (attempt {attempt})" if attempt is not None else "",
    )
    return sc_count
