## Why

After 2 days of live orchestration on sales-raketa v3, `wt-orchestrate` accumulated 35 adhoc fix commits and diverged significantly from its specs. A comprehensive audit found: 10 known bugs in the code, 11 features implemented without specs, 7 contradictions between specs and code, and 6 spec items that were never implemented. The most critical issue — an infinite replan loop burning ~50-100k tokens per 5-minute cycle — was caused by the interaction of two separately-correct adhoc fixes that together create a logic contradiction.

The orchestrator cannot be safely restarted for the next project until these issues are resolved and the specs are synchronized with reality.

## What Changes

### Bug Fixes (10 bugs from audit)

1. **Infinite replan loop on failed changes** — `failed` status is terminal in monitor_loop (line 2792) but excluded from `completed_changes` in replan (line 2855). When replan LLM fails/timeouts (rc=2), there's no max retry limit → infinite loop. Fix: add `MAX_REPLAN_RETRIES=3`, after which declare done-with-warnings.

2. **Verify failure path missing retry_context** — `handle_change_done()` line 3451: when `/opsx:verify` fails, `resume_change()` is called without setting `retry_context`. Agent gets zero info about what verify found. Fix: store verify output in `retry_context` before resume (same pattern as test-failure path at line 3234).

3. **Double checkpoint on completion** — `trigger_checkpoint("completion")` at line 2833 blocks until approved, then falls through to next loop iteration which immediately triggers another checkpoint. Fix: add `break` after `trigger_checkpoint("completion")`.

4. **Stale-running path calls resume without status update** — `poll_change()` line 2997: stale running change gets `resume_change()` called but status stays `"running"`, so next poll cycle calls resume again (parallel resumes). Fix: set status to `"stalled"` before resume, matching the normal stall path.

5. **stall_count not reset after successful resume** — `resume_stalled_changes()` at line 3684: calls `resume_change()` but never resets `stall_count`. If change stalls again later for a different reason, the accumulated count may cause premature failure. Fix: reset `stall_count` to 0 when setting status back to `"running"`.

6. **auto_replan stdout floods terminal** — `cmd_plan` at line 2889: only stderr is redirected (`2>>"$LOG_FILE"`), info/progress messages go to terminal interleaved with monitor output. Fix: redirect both stdout and stderr (`&>>"$LOG_FILE"`).

7. **Nested function `_try_merge` state pollution** — `retry_merge_queue()` line 3637: bash function defined inside another function persists globally. Fix: move to top-level or inline.

8. **openspec new change errors swallowed** — `dispatch_change()` line 2458: `openspec new change "$change_name" 2>/dev/null || true`. Fix: log the actual error, only continue if the directory was successfully created.

9. **wt-close may operate on wrong project** — `cleanup_worktree()`: `wt-close` called without explicit project path context. Fix: pass project path explicitly or cd to project root before calling.

10. **Indentation bug** — `orch_gate_stats` at line 2837 has wrong indentation level, potentially in wrong block. Fix: verify correct block placement and fix indentation.

### Token Efficiency (new)

11. **Spec summarization cache** — `auto_replan_cycle()` re-summarizes the spec on every retry even when `brief_hash` hasn't changed. Fix: cache summarization result keyed by brief_hash, skip if cache hit.

12. **Failed change build-fix retry path** — Instead of full replan for build failures, offer a lighter retry: resume the agent in the worktree with build error context to fix the specific type error. Much cheaper than a new decomposition.

### Spec Synchronization (11 unspecced features + 7 contradictions)

Update orchestration specs to reflect reality:

13. **Document `auto_replan`** — auto_replan_cycle(), replan_cycle tracking, `auto_replan: true` directive. Currently the biggest undocumented feature.

14. **Document `--time-limit`** — parse_duration(), format_duration(), active-seconds tracking, DEFAULT_TIME_LIMIT="5h". Entirely adhoc.

15. **Document `check_base_build` + `fix_base_build_with_llm`** — Main branch build verification and LLM-based auto-fix. 3 functions (~180 lines) with no spec.

16. **Document stale loop-state detection** — 5-minute mtime check in poll_change(). Not in any spec.

17. **Document retroactive worktree bootstrap** — bootstrap_worktree() called from dispatch_change() for existing worktrees.

18. **Document memory audit** — orch_memory_audit() periodic health check.

19. **Document BASE_BUILD cache** — invalidation after merge.

20. **Document find_existing_worktree()** — Flexible worktree path discovery.

21. **Fix verify gate step order in spec** — Code order is tests→build→test_files→review→verify (optimized). Spec says tests→review→verify→test_files→build. Update spec to match code (the code order is better).

22. **Fix token budget behavior in spec** — Code does wait-mode (skip dispatch), not checkpoint. Update spec to match code behavior.

23. **Fix stall memory save timing in spec** — Off-by-one: spec says attempt 3/3, code fires at attempt 4 (the give-up branch). Align.

24. **Fix Ralph launch flags in spec** — Code passes task description as positional arg + `--label` + `--model opus`. Spec only shows `--max 30 --done openspec`.

25. **Fix merge approach in spec** — Code uses `wt-merge --llm-resolve` directly, no dry-run pre-check. Update spec.

26. **Document verify_retry_count integer** — Spec says boolean `verify_retried`. Code uses integer + max_verify_retries. Update spec.

### Low Priority (spec items not implemented — document as deferred)

27. **Mark checkpoint 24h reminder as deferred** — Spec requirement, not implemented, low value.
28. **Mark self-test fixtures as deferred** — Level 2-4 tests, fixture files. Not worth blocking stabilization.
29. **Mark ASCII DAG in `--show` as deferred** — Nice to have, not critical.

## Capabilities

### Modified Capabilities
- `orchestration-engine`: Bug fixes to monitor_loop, replan, poll_change, checkpoint handling
- `verify-gate`: Fix retry_context passthrough on verify failure, step order spec update
- `verify-retry-context`: Fix stall_count reset, stale-running status update
- `orchestrator-memory`: Fix memory audit timing, add spec summary cache

### New Capabilities
- `replan-safety`: Max replan retries, failed-change deduplication, spec summary caching
- `build-fix-retry`: Lightweight retry path for build failures (cheaper than full replan)
