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
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import glob as glob_mod
import os
import shutil

import re

from .state import Change, GateRetryEntry, locked_state, update_change_field
from .truncate import smart_truncate, smart_truncate_structured


# Per-gate output storage budgets. E2E gets a much larger budget because
# Playwright's numbered failure list + summary can exceed the default 2000
# bytes, and truncating it hides the failures from retry context.
# See OpenSpec change: fix-e2e-gate-timeout-masking.
_GATE_OUTPUT_BUDGETS = {
    "e2e": 32000,
}
_DEFAULT_GATE_OUTPUT_BUDGET = 2000

logger = logging.getLogger(__name__)


# Pattern that matches Playwright's numbered failure list entries —
# "  1) [chromium] › tests/e2e/foo.spec.ts:45 › REQ-FOO-001"
# Preserved in the middle of truncated e2e output so failure IDs survive
# state storage even on suites with 50+ failures.
#
# Note: this pattern intentionally differs from _extract_e2e_failure_ids in
# modules/web/set_project_web/gates.py. That one CAPTURES the "<spec>:<line>"
# substring for baseline comparison; this one only needs to MATCH the entry
# line so smart_truncate_structured preserves it. Stopping at `.spec.\w+`
# (without the `:line_number` suffix) is deliberate — we only care whether
# the line exists, not what the capture group returns.
_PLAYWRIGHT_FAIL_PATTERN = re.compile(
    r"^\s*\d+\)\s+\[.*?\]\s+[›»]\s+[^\s:]+\.spec\.\w+",
    re.MULTILINE,
)


def _truncate_gate_output(gate_name: str, output: str) -> str:
    """Truncate gate output with per-gate budgets and pattern-preserving logic for e2e."""
    if not output:
        return output
    budget = _GATE_OUTPUT_BUDGETS.get(gate_name, _DEFAULT_GATE_OUTPUT_BUDGET)
    if gate_name == "e2e":
        # Preserve numbered failure lines so retry context keeps the failure IDs.
        return smart_truncate_structured(output, budget, keep_patterns=_PLAYWRIGHT_FAIL_PATTERN)
    return smart_truncate(output, budget)


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
    # Infrastructure-failure signal — distinguishes "LLM returned FAIL verdict"
    # from "LLM exhausted max_turns / timed out". Surfaced on VERIFY_GATE event
    # data so operators can filter infra anomalies from real code faults.
    infra_fail: bool = False
    # Short reason string accompanying infra_fail (e.g. "max_turns", "timeout")
    terminal_reason: str = ""


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
    if pending:
        logger.warning("Gate order: %d unresolvable gates appended before end: %s",
                       len(pending), [g.name for g in pending])
    placed.extend(pending)
    placed.extend(before_end_gates)
    placed.extend(end_gates)
    logger.info("Gate order resolved: %s", [g.name for g in placed])
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
        parallel_groups: Optional[list[set[str]]] = None,
        profile: Any = None,
        max_consecutive_cache_uses: int = 2,
    ) -> None:
        self.gc = gc
        self.state_file = state_file
        self.change_name = change_name
        self.change = change
        self.max_retries = max_retries
        self.event_bus = event_bus
        # Parallel-group hint from the project profile (section 8 of
        # fix-replan-stuck-gate-and-decomposer). Gates whose names all fall
        # into the same group (and are registered adjacently) are dispatched
        # concurrently via a ThreadPoolExecutor. Empty/None → serial.
        self.parallel_groups: list[set[str]] = [
            set(g) for g in (parallel_groups or [])
        ]
        # Per-gate retry policy plumbing (section 12 of
        # fix-replan-stuck-gate-and-decomposer). `profile` may be None for
        # CoreProfile / no-profile paths — in that case every gate behaves
        # as `"always"` (no caching, no scoping).
        self.profile = profile
        self.max_consecutive_cache_uses = max(1, int(max_consecutive_cache_uses))
        self._gate_retry_policy: dict[str, str] = {}
        if profile is not None and hasattr(profile, "gate_retry_policy"):
            try:
                self._gate_retry_policy = dict(profile.gate_retry_policy() or {})
            except Exception:
                logger.warning(
                    "gate_retry_policy() threw — defaulting all gates to always",
                    exc_info=True,
                )

        self._gates: list[_GateEntry] = []
        self.results: list[GateResult] = []
        self.stopped = False
        self.stop_action: str = ""  # "retry" or "failed"
        self.stop_gate: str = ""  # which gate caused the stop
        self._verify_retry_count = change.verify_retry_count
        # Tracks which gate names ran as one parallel batch — the verifier
        # reads this when emitting VERIFY_GATE so consumers can see the
        # concurrency decision (parallel_group: [...] field).
        self.parallel_group_runs: list[list[str]] = []
        # Scoped-subset filter passed to gate executors at runtime (e.g.
        # Playwright spec subset). Gates read this via kwargs from the
        # register-time closure (see verifier.py register call sites).
        self._gate_scoped_subset: dict[str, list[str]] = {}
        # Tracks which gates were cached this run so commit_results can
        # persist updated tracking state.
        self._gate_cached_this_run: dict[str, str] = {}  # gate_name → reuse reason
        self._gate_full_ran_this_run: set[str] = set()
        # Memoized retry diff files (current HEAD vs prior full-run
        # baseline). `None` means the diff could not be computed — safe
        # default is to force a full run (see _retry_diff_files docstring).
        self._retry_diff_cache: dict[str, Optional[list[str]]] = {}

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
        logger.debug("Gate registered: %s for %s (retry_counter=%s, extra_retries=%d)",
                      name, self.change_name, own_retry_counter or "shared", extra_retries)

    def _retry_diff_files(self, baseline_sha: str) -> Optional[list[str]]:
        """Return files touched since `baseline_sha` in the worktree.

        Returns `None` on failure (missing baseline, git error, non-zero
        exit, bad worktree path). A `None` return is a cache-miss signal:
        callers MUST NOT treat it as "no files changed" — the safe default
        is to invalidate the cache and run fully. This distinction is
        load-bearing (see review of commit 869792fb, CRITICAL-1).

        Returns `[]` only when git succeeded and reported zero changes.

        Memoized per baseline so multiple gates with the same prior-full-run
        commit don't re-shell out to git.
        """
        if not baseline_sha or not self.change.worktree_path:
            return None
        if baseline_sha in self._retry_diff_cache:
            return self._retry_diff_cache[baseline_sha]
        try:
            out = subprocess.run(
                ["git", "-C", self.change.worktree_path,
                 "diff", "--name-only", baseline_sha, "HEAD"],
                capture_output=True, text=True, timeout=10,
            )
            if out.returncode != 0:
                logger.warning(
                    "retry_diff_files(%s) git exited %d for %s: %s",
                    baseline_sha[:8], out.returncode, self.change_name,
                    (out.stderr or "").strip()[:200],
                )
                self._retry_diff_cache[baseline_sha] = None  # type: ignore[assignment]
                return None
            files = [line for line in out.stdout.splitlines() if line.strip()]
        except Exception as exc:
            logger.warning(
                "retry_diff_files(%s) failed for %s: %s",
                baseline_sha[:8], self.change_name, exc,
            )
            self._retry_diff_cache[baseline_sha] = None  # type: ignore[assignment]
            return None
        self._retry_diff_cache[baseline_sha] = files
        logger.debug(
            "retry_diff_files(%s..HEAD) for %s: %d files",
            baseline_sha[:8], self.change_name, len(files),
        )
        return files

    def _diff_touches_scope(
        self, diff_files: Optional[list[str]], scope_globs: list[str],
    ) -> bool:
        """Return True if any diff file matches any scope glob.

        Note: callers MUST distinguish between `diff_files=None` (git
        failure → force invalidate cache) and `diff_files=[]` (no
        changes → cache can be reused). This helper returns False for
        both cases; `_try_cache_reuse` handles the `None` path before
        calling in.
        """
        if not scope_globs or not diff_files:
            return False
        import fnmatch
        for pattern in scope_globs:
            for f in diff_files:
                # fnmatch treats `**` as `*` — Path-style `**` matching requires
                # splitting the pattern. Use pathspec-style comparison via
                # re-rooting the glob: pattern `src/**` should match `src/a/b`.
                if fnmatch.fnmatch(f, pattern):
                    return True
                # Manual `**` handling: replace `**/` with `*/.../*/` match by
                # checking prefix+suffix against segments.
                if "**" in pattern:
                    parts = pattern.split("**", 1)
                    prefix = parts[0].rstrip("/")
                    suffix = parts[1].lstrip("/")
                    if f.startswith(prefix):
                        remainder = f[len(prefix):].lstrip("/")
                        if not suffix:
                            return True
                        if fnmatch.fnmatch(remainder, suffix) or fnmatch.fnmatch(
                            remainder.rsplit("/", 1)[-1] if "/" in remainder else remainder,
                            suffix,
                        ):
                            return True
        return False

    _NEW_API_SURFACE_PATTERNS = [
        re.compile(r"^\+\s*export\s+(async\s+)?function\s+\w+", re.MULTILINE),
        re.compile(r"^\+\s*export\s+const\s+\w+\s*=\s*async", re.MULTILINE),
        re.compile(r"^\+\s*model\s+\w+\s*\{", re.MULTILINE),
        re.compile(
            r"^\+\s*export\s+async\s+function\s+(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\b",
            re.MULTILINE,
        ),
    ]

    def _diff_has_new_api_surface(self, baseline_sha: str) -> bool:
        """Scan the retry diff for new exported APIs / Prisma models.

        Returns True if the unified diff contains any `+export function`,
        `+export const X = async`, `+model X {`, or `+export async function
        (GET|POST|…)` added line. These signals indicate a new public API
        surface that a cached verdict cannot reason about.
        """
        if not baseline_sha or not self.change.worktree_path:
            return False
        try:
            out = subprocess.run(
                ["git", "-C", self.change.worktree_path,
                 "diff", "--unified=0", baseline_sha, "HEAD"],
                capture_output=True, text=True, timeout=15,
            )
            text = out.stdout or ""
        except Exception:
            return False
        for pat in self._NEW_API_SURFACE_PATTERNS:
            if pat.search(text):
                return True
        return False

    def _policy_for(self, gate_name: str) -> str:
        """Resolve retry policy for a gate. Defaults to `always`."""
        return self._gate_retry_policy.get(gate_name, "always")

    def _prior_tracking(self, gate_name: str) -> GateRetryEntry:
        """Return (or create) the per-gate tracking entry on self.change."""
        tracking = self.change.gate_retry_tracking
        if gate_name not in tracking:
            tracking[gate_name] = GateRetryEntry()
        return tracking[gate_name]

    def _try_cache_reuse(self, gate_name: str) -> Optional[tuple[str, str]]:
        """Check whether `gate_name` can reuse its prior verdict.

        Returns (reason, prior_sha) on cache hit (reason explains why it was
        reused — for logging), or None on cache miss (caller runs full).
        """
        # On the first verify-pipeline run (verify_retry_index==0), never
        # cache — this is the "first run ignores policy" rule.
        if int(self.change.verify_retry_index or 0) == 0:
            return None

        entry = self._prior_tracking(gate_name)
        prior_sha = entry.last_verdict_sha
        if not prior_sha:
            # No prior full run to reuse; must run fully.
            return None

        # Cap: after N consecutive cache reuses, force a full run.
        if entry.consecutive_cache_uses >= self.max_consecutive_cache_uses:
            logger.info(
                "Cache invalidated for %s on %s: cache-use cap reached (%d >= %d)",
                gate_name, self.change_name,
                entry.consecutive_cache_uses, self.max_consecutive_cache_uses,
            )
            return None

        # Retry-diff computation. A None result (git failure, bad
        # worktree) MUST force a full run — the safe default when we
        # can't tell what changed is to re-verify, not to assume clean.
        diff_files = self._retry_diff_files(prior_sha)
        if diff_files is None:
            logger.info(
                "Cache invalidated for %s on %s: retry-diff-unavailable",
                gate_name, self.change_name,
            )
            return None

        # Scope check: does the retry diff touch any cache-scope glob?
        scope_globs: list[str] = []
        if self.profile is not None and hasattr(self.profile, "gate_cache_scope"):
            try:
                scope_globs = list(self.profile.gate_cache_scope(gate_name) or [])
            except Exception:
                scope_globs = []
        if self._diff_touches_scope(diff_files, scope_globs):
            logger.info(
                "Cache invalidated for %s on %s: diff-touches-scope",
                gate_name, self.change_name,
            )
            return None

        # New API surface check: block cache reuse if the diff adds exports.
        if self._diff_has_new_api_surface(prior_sha):
            logger.info(
                "Cache invalidated for %s on %s: new-api-surface-detected",
                gate_name, self.change_name,
            )
            return None

        return ("reuse", prior_sha)

    def _try_scoped_run(
        self, gate_name: str,
    ) -> Optional[list[str]]:
        """Return a scoped subset for a `"scoped"`-policy gate, or None to
        fall through to cached policy.
        """
        if int(self.change.verify_retry_index or 0) == 0:
            return None
        if self.profile is None or not hasattr(self.profile, "gate_scope_filter"):
            return None

        entry = self._prior_tracking(gate_name)
        prior_sha = entry.last_verdict_sha
        if not prior_sha:
            return None
        diff_files = self._retry_diff_files(prior_sha)
        # None → diff unavailable → force full run; empty list → no changes
        # → nothing to scope, also force full (caller falls through).
        if not diff_files:
            return None
        try:
            subset = self.profile.gate_scope_filter(gate_name, diff_files)
        except Exception:
            logger.warning(
                "gate_scope_filter(%s) threw for %s — falling through",
                gate_name, self.change_name, exc_info=True,
            )
            subset = None
        if not subset:
            return None

        # verify-gate-resilience-fixes: filter the candidate paths against
        # actual filesystem existence BEFORE entering scoped-subset mode.
        # Without this, the gate logs `Scoped gate: e2e running on N subset
        # items: [bogus_path]` then falls back to the full suite, wasting
        # ~30 min per retry on a no-op spawn. If 0 valid paths remain, return
        # None so the caller falls through to cached/full policy.
        from pathlib import Path as _Path
        wt_path = self.change.worktree_path or ""
        if wt_path:
            _wt = _Path(wt_path)
            existing = [s for s in subset if (_wt / s).exists()]
            dropped = [s for s in subset if (_wt / s).exists() is False]
            if dropped:
                logger.info(
                    "Scoped subset: filtered %d non-existent path(s) for %s/%s: %s",
                    len(dropped), self.change_name, gate_name, dropped,
                )
            if not existing:
                logger.info(
                    "Scoped subset: 0 valid paths after existence filter for %s/%s — "
                    "falling through to cached/full policy",
                    self.change_name, gate_name,
                )
                return None
            subset = existing

        # Scoped runs still respect the cache-use cap — 2 consecutive
        # scoped retries, then the 3rd forces a full run.
        if entry.consecutive_cache_uses >= self.max_consecutive_cache_uses:
            logger.info(
                "Scoped run forced to full for %s on %s: cache-use cap",
                gate_name, self.change_name,
            )
            return None
        return list(subset)

    def _emit_gate_cached(self, gate_name: str, prior_sha: str) -> None:
        """Emit GATE_CACHED event for observability."""
        if self.event_bus is None:
            return
        try:
            self.event_bus.emit(
                "GATE_CACHED",
                change=self.change_name,
                data={
                    "gate": gate_name,
                    "prior_sha": prior_sha,
                    "retry_index": int(self.change.verify_retry_index or 0),
                },
            )
        except Exception as exc:
            logger.debug(
                "GATE_CACHED emit failed for %s/%s: %s",
                self.change_name, gate_name, exc,
            )

    def _record_cache_reuse(self, entry: _GateEntry, prior_sha: str) -> Optional[str]:
        """Record a cache reuse: append a GateResult with the prior
        verdict's status, emit GATE_CACHED, and mark the gate in
        self._gate_cached_this_run.

        Faithfully replays the prior verdict (pass/fail/warn-fail/skipped)
        — if the prior run failed, the cache reuse must also fail, else a
        fixed-diff retry would silently let a failing gate pass (see
        review of commit 869792fb, CRITICAL-2).

        Returns the pipeline stop action ("retry" | "failed") when the
        replayed verdict blocks, or None otherwise.
        """
        tracking = self._prior_tracking(entry.name)
        prior_verdict = tracking.last_verdict or "pass"

        result = GateResult(
            gate_name=entry.name,
            status=prior_verdict,
            output=f"cache reuse from {prior_sha[:8]} (verdict={prior_verdict})",
            duration_ms=0,
        )
        self._persist_gate_result(entry, result, 0)
        self._gate_cached_this_run[entry.name] = prior_sha
        self._emit_gate_cached(entry.name, prior_sha)
        logger.info(
            "Verify gate: %s CACHED for %s (prior=%s, verdict=%s)",
            entry.name, self.change_name, prior_sha[:8], prior_verdict,
        )
        return self._finalize_result(entry, result, 0)

    def _parallel_group_for(self, gate_name: str) -> Optional[frozenset[str]]:
        """Return the parallel group (as a frozenset) that contains gate_name,
        or None if the gate is not in any parallel group."""
        for g in self.parallel_groups:
            if gate_name in g:
                return frozenset(g)
        return None

    def _execute_single_entry(self, entry: _GateEntry) -> tuple[GateResult, int]:
        """Execute one gate executor. Returns (result, elapsed_ms).

        Does NOT handle skip, post-gate state writes, or retry logic — the
        caller stitches those back together after the (possibly parallel)
        batch finishes.
        """
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
        return result, elapsed_ms

    def run(self) -> str:
        """Execute all registered gates in order.

        Returns:
            "continue" — all gates passed (or non-blocking failures)
            "retry"    — blocking failure, retry dispatched
            "failed"   — blocking failure, retries exhausted
        """
        # Snapshot HEAD before gates run — used by engine to detect progress
        # when ralph exits with stopped/stuck (FIX 1).
        if self.change.worktree_path:
            try:
                head = subprocess.run(
                    ["git", "-C", self.change.worktree_path, "rev-parse", "HEAD"],
                    capture_output=True, text=True, timeout=5,
                ).stdout.strip()
                if head:
                    update_change_field(
                        self.state_file, self.change_name,
                        "last_gate_commit", head,
                    )
            except Exception as exc:
                logger.debug("last_gate_commit snapshot failed for %s: %s", self.change_name, exc)

        # Iterate with an index so we can advance past a parallel batch in one step.
        i = 0
        while i < len(self._gates):
            if self.stopped:
                break

            entry = self._gates[i]

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
                i += 1
                continue

            # Per-gate retry policy (section 12). `cached`: try to reuse
            # prior verdict; `scoped`: try to shard the gate; `always`:
            # normal execution. The policy is consulted only on
            # verify_retry_index >= 1 (first run always runs fully).
            _policy = self._policy_for(entry.name)
            if _policy == "scoped":
                _subset = self._try_scoped_run(entry.name)
                if _subset is not None:
                    # Record subset for the gate executor to consume.
                    self._gate_scoped_subset[entry.name] = _subset
                    logger.info(
                        "Scoped gate: %s running on %d subset item(s) for %s: %s",
                        entry.name, len(_subset), self.change_name, _subset,
                    )
                else:
                    # Fall through to cached policy (per D10).
                    _cache_hit = self._try_cache_reuse(entry.name)
                    if _cache_hit is not None:
                        _reason, _prior_sha = _cache_hit
                        _action = self._record_cache_reuse(entry, _prior_sha)
                        i += 1
                        if _action is not None:
                            return _action
                        continue
            elif _policy == "cached":
                _cache_hit = self._try_cache_reuse(entry.name)
                if _cache_hit is not None:
                    _reason, _prior_sha = _cache_hit
                    _action = self._record_cache_reuse(entry, _prior_sha)
                    i += 1
                    if _action is not None:
                        return _action
                    continue

            # Parallel-batch detection: if this gate is in a parallel group
            # shared with one or more adjacent registered gates (each also
            # should_run), dispatch them all concurrently. The registration
            # order is preserved for stop_gate selection.
            group = self._parallel_group_for(entry.name)
            batch: list[_GateEntry] = [entry]
            if group is not None:
                j = i + 1
                while j < len(self._gates):
                    nxt = self._gates[j]
                    if nxt.name in group and self.gc.should_run(nxt.name):
                        # Don't pull in a peer that was just cache-reused.
                        if nxt.name in self._gate_cached_this_run:
                            j += 1
                            continue
                        batch.append(nxt)
                        j += 1
                    else:
                        break

            if len(batch) > 1:
                action = self._run_parallel_batch(batch)
                i += len(batch)
                if action is not None:
                    return action
                continue

            # Single-gate execution (default path)
            result, elapsed_ms = self._execute_single_entry(entry)
            self._gate_full_ran_this_run.add(entry.name)
            i += 1
            self._persist_gate_result(entry, result, elapsed_ms)
            action = self._finalize_result(entry, result, elapsed_ms)
            if action is not None:
                return action

        return "continue"

    _GATE_STATE_FIELDS = {
        "build": "build_result", "test": "test_result",
        "e2e": "e2e_result", "smoke": "smoke_result",
        "review": "review_result", "scope_check": "scope_check_result",
        "rules": "rules_result", "e2e_coverage": "e2e_coverage_result",
    }
    _GATE_MS_FIELDS = {
        "build": "gate_build_ms", "test": "gate_test_ms",
        "e2e": "gate_e2e_ms", "review": "gate_review_ms",
        "smoke": "gate_smoke_ms", "scope_check": "gate_scope_check_ms",
        "rules": "gate_rules_ms", "e2e_coverage": "gate_e2e_coverage_ms",
    }
    _GATE_OUTPUT_FIELDS = {
        "build": "build_output", "test": "test_output", "e2e": "e2e_output",
        "review": "review_output", "smoke": "smoke_output",
        "scope_check": "scope_check_output", "rules": "rules_output",
        "e2e_coverage": "e2e_coverage_output",
    }

    def _persist_gate_result(
        self, entry: _GateEntry, result: GateResult, elapsed_ms: int,
    ) -> None:
        """Archive artifacts + write gate-result fields to state."""
        # Archive test-results/ after every gate run that produced them
        if entry.name in ("e2e", "test", "smoke"):
            try:
                _attempt_num = (
                    self.change.extras.get(entry.own_retry_counter, 0)
                    if entry.own_retry_counter
                    else self._verify_retry_count
                ) + 1
                _archive_attempt_artifacts(
                    self.change.worktree_path,
                    self.change_name,
                    attempt=_attempt_num,
                )
            except Exception as exc:
                logger.debug(
                    "Post-gate archive (%s) failed for %s: %s",
                    entry.name, self.change_name, exc,
                )

        state_field = self._GATE_STATE_FIELDS.get(entry.name)
        ms_field = self._GATE_MS_FIELDS.get(entry.name)
        output_field = self._GATE_OUTPUT_FIELDS.get(entry.name)
        if state_field and self.state_file:
            update_change_field(
                self.state_file, self.change_name, state_field, result.status,
            )
        if ms_field and self.state_file:
            update_change_field(
                self.state_file, self.change_name, ms_field, elapsed_ms,
            )
        if output_field and self.state_file and result.output:
            update_change_field(
                self.state_file, self.change_name, output_field,
                _truncate_gate_output(entry.name, result.output),
            )

    def _finalize_result(
        self, entry: _GateEntry, result: GateResult, elapsed_ms: int,
    ) -> Optional[str]:
        """Append a completed result and decide whether to stop.

        Returns None on continue, "retry" or "failed" on a blocking stop.
        """
        if result.status == "pass":
            self.results.append(result)
            logger.info(
                "Verify gate: %s passed for %s (%dms)",
                entry.name, self.change_name, elapsed_ms,
            )
            return None

        if result.status == "fail":
            if self.gc.is_blocking(entry.name):
                self.results.append(result)
                return self._handle_blocking_failure(entry, result)
            # Non-blocking: convert to warn-fail
            result.status = "warn-fail"
            self.results.append(result)
            logger.warning(
                "Verify gate: %s failed for %s — non-blocking (gate=%s)",
                entry.name, self.change_name,
                self.gc.get(entry.name, "?"),
            )
            return None

        # "skipped", "warn-fail", or other — pass through
        self.results.append(result)
        return None

    def _run_parallel_batch(self, batch: list[_GateEntry]) -> Optional[str]:
        """Dispatch a batch of independent gates concurrently.

        Returns None on continue, or "retry"/"failed" on the earliest
        blocking failure. When multiple gates fail in the batch the
        earliest-registered one becomes `stop_gate`, but retry_context is
        merged from ALL failed gates so the retry agent sees both finding
        sets (task 8.6).
        """
        from concurrent.futures import ThreadPoolExecutor

        names = [e.name for e in batch]
        self.parallel_group_runs.append(names)
        logger.info(
            "Verify gate: dispatching %d gates in parallel for %s: %s",
            len(batch), self.change_name, names,
        )

        results_by_idx: dict[int, tuple[GateResult, int]] = {}
        with ThreadPoolExecutor(max_workers=len(batch)) as pool:
            futures = {
                pool.submit(self._execute_single_entry, entry): idx
                for idx, entry in enumerate(batch)
            }
            # Wait for every future. _execute_single_entry already catches
            # per-gate exceptions and returns a fail GateResult; a raise
            # from .result() here would be hard infra (OOM / pool shutdown)
            # — surface it as a fail slot so VERIFY_GATE can still emit.
            for fut, idx in futures.items():
                try:
                    results_by_idx[idx] = fut.result()
                except Exception as exc:
                    logger.error(
                        "Parallel gate future raised unexpectedly: %s",
                        exc, exc_info=True,
                    )
                    _entry = batch[idx]
                    results_by_idx[idx] = (
                        GateResult(
                            gate_name=_entry.name,
                            status="fail",
                            output=f"future raised: {exc}",
                        ),
                        0,
                    )

        # Persist each in registration order so state writes stay deterministic.
        for idx, entry in enumerate(batch):
            result, elapsed_ms = results_by_idx[idx]
            self._persist_gate_result(entry, result, elapsed_ms)
            self._gate_full_ran_this_run.add(entry.name)

        # Outcome: find the earliest-registered blocking failure.
        earliest_fail_idx = None
        merged_retry_context_parts: list[str] = []
        for idx, entry in enumerate(batch):
            result, _ = results_by_idx[idx]
            if result.status == "fail" and self.gc.is_blocking(entry.name):
                if earliest_fail_idx is None:
                    earliest_fail_idx = idx
                if result.retry_context:
                    merged_retry_context_parts.append(
                        f"## From gate: {entry.name}\n{result.retry_context}"
                    )

        if earliest_fail_idx is None:
            # No blocking failure — finalize each result in registration order
            # and continue. Non-blocking fails get warn-fail conversion here.
            for idx, entry in enumerate(batch):
                result, elapsed_ms = results_by_idx[idx]
                action = self._finalize_result(entry, result, elapsed_ms)
                if action is not None:
                    return action
            return None

        # Blocking failure in the batch. First, append the non-failing and
        # non-blocking-fail results (in order) so they are visible to
        # commit_results. Then merge retry contexts from all failed gates and
        # call _handle_blocking_failure on the earliest failer.
        for idx, entry in enumerate(batch):
            if idx == earliest_fail_idx:
                continue
            result, elapsed_ms = results_by_idx[idx]
            if result.status == "fail":
                if self.gc.is_blocking(entry.name):
                    # Record peer blocking failures — don't re-run budget logic
                    self.results.append(result)
                else:
                    result.status = "warn-fail"
                    self.results.append(result)
            else:
                self.results.append(result)

        stop_result, _ = results_by_idx[earliest_fail_idx]
        stop_entry = batch[earliest_fail_idx]
        # Merge retry contexts — earliest-registered is first, then peers
        if len(merged_retry_context_parts) > 1:
            stop_result.retry_context = "\n\n".join(merged_retry_context_parts)
        self.results.append(stop_result)
        return self._handle_blocking_failure(stop_entry, stop_result)

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
            # Archive test-results/ for THIS attempt before the agent's next
            # run overwrites it. Otherwise the dashboard only shows the final
            # (passing) attempt's artifacts — all intermediate failure
            # screenshots and error-context files are lost at redispatch.
            # The attempt number we persist is current_count + 1 because it
            # was just incremented above as the next attempt's counter.
            try:
                _archive_attempt_artifacts(
                    self.change.worktree_path,
                    self.change_name,
                    attempt=current_count,  # the attempt that just FAILED
                )
            except Exception as exc:
                logger.warning(
                    "Archive attempt-%d artifacts for %s failed: %s",
                    current_count, self.change_name, exc,
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
                        c.extras[f"{r.gate_name}_output"] = _truncate_gate_output(r.gate_name, r.output)

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

                # Persist per-gate retry tracking (section 12). Full runs
                # capture current HEAD as the new baseline + reset cache
                # counter. Cache reuses increment the counter and keep
                # the prior baseline.
                _head_sha = ""
                if self.change.worktree_path:
                    try:
                        _head_sha = subprocess.run(
                            ["git", "-C", self.change.worktree_path,
                             "rev-parse", "HEAD"],
                            capture_output=True, text=True, timeout=5,
                        ).stdout.strip()
                    except Exception:
                        _head_sha = ""

                # Build a name → verdict map from this run's results so
                # we can persist last_verdict faithfully per gate.
                _verdicts_this_run: dict[str, str] = {
                    r.gate_name: r.status for r in self.results if r.gate_name
                }

                _tracking = dict(c.gate_retry_tracking or {})
                for gate_name in self._gate_full_ran_this_run:
                    _entry = _tracking.get(gate_name) or GateRetryEntry()
                    _entry.consecutive_cache_uses = 0
                    if _head_sha:
                        _entry.last_verdict_sha = _head_sha
                    _entry.last_run_retry_index = int(
                        self.change.verify_retry_index or 0,
                    )
                    # Record the actual verdict so future cache reuses
                    # replay the correct outcome (not an assumed pass).
                    _v = _verdicts_this_run.get(gate_name)
                    if _v:
                        _entry.last_verdict = _v
                    _tracking[gate_name] = _entry
                for gate_name in self._gate_cached_this_run:
                    _entry = _tracking.get(gate_name) or GateRetryEntry()
                    _entry.consecutive_cache_uses += 1
                    _tracking[gate_name] = _entry
                c.gate_retry_tracking = _tracking

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


def _archive_attempt_artifacts(
    wt_path: str,
    change_name: str,
    attempt: int,
) -> int:
    """Copy the worktree's `test-results/` into `<runtime>/artifacts/<change>/attempt-<N>/`.

    Called right before a gate-retry dispatches so the agent's next run does
    not overwrite this attempt's failure screenshots, error-context.md files,
    and Playwright traces. Without this archive the dashboard's screenshots
    endpoint only surfaces the *final* (passing) attempt's artifacts — every
    intermediate failure is lost when the agent re-runs Playwright.

    Returns the number of files archived (0 on any error — non-fatal).
    """
    if not wt_path or attempt <= 0:
        return 0
    src = os.path.join(wt_path, "test-results")
    if not os.path.isdir(src):
        return 0
    try:
        from .paths import SetRuntime
        rt = SetRuntime()
        base = os.path.join(rt.screenshots_dir, "attempts", change_name)
    except Exception:
        base = f"set/orchestration/attempts/{change_name}"
    dest = os.path.join(base, f"attempt-{attempt}", "test-results")
    os.makedirs(dest, exist_ok=True)
    try:
        shutil.copytree(src, dest, dirs_exist_ok=True)
    except Exception as exc:
        logger.warning(
            "Archive attempt-%d for %s: copytree failed: %s",
            attempt, change_name, exc,
        )
        return 0
    n = len(glob_mod.glob(os.path.join(dest, "**", "*"), recursive=True))
    logger.info(
        "Archive attempt-%d for %s: %d files preserved at %s",
        attempt, change_name, n, dest,
    )
    return n
