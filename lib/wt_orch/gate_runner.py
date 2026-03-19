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
    ) -> None:
        """Register a gate to execute. Gates run in registration order."""
        self._gates.append(_GateEntry(
            name=name,
            executor=executor,
            own_retry_counter=own_retry_counter,
            extra_retries=extra_retries,
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
                        entry.name, self.change_name, getattr(self.gc, entry.name, "?"),
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

        Returns a summary dict for event emission.
        """
        # Build field updates
        gate_field_map = {
            "build": ("build_result", "gate_build_ms"),
            "test": ("test_result", "gate_test_ms"),
            "e2e": ("e2e_result", "gate_e2e_ms"),
            "review": ("review_result", "gate_review_ms"),
            "spec_verify": ("spec_coverage_result", "gate_verify_ms"),
        }

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
                    elif r.gate_name == "scope":
                        c.extras["scope_check"] = r.status
                    elif r.gate_name == "test_files":
                        c.extras["has_tests"] = r.status == "pass"
                    elif r.gate_name == "rules":
                        c.extras["rules_result"] = r.status

                    # Store output for key gates
                    if r.output and r.gate_name in ("test", "build", "review", "e2e"):
                        c.extras[f"{r.gate_name}_output"] = r.output[:2000]

                    # Store stats — prefer dataclass field, fall back to extras
                    if r.stats and r.gate_name in ("test", "e2e"):
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
    """Collect Playwright test-results screenshots to a consistent WtRuntime path.

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

    # Resolve destination via WtRuntime, fall back to legacy path
    try:
        from .paths import WtRuntime
        rt = WtRuntime()
        if category == "smoke":
            base_dir = rt.smoke_screenshots_dir(change_name)
        else:
            base_dir = os.path.join(rt.screenshots_dir, category, change_name)
    except Exception:
        base_dir = f"wt/orchestration/{category}-screenshots/{change_name}"

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
