# Design: merge-on-branch

## Context

The orchestration pipeline currently follows a "verify-then-merge" pattern:
1. Agent completes work on feature branch (worktree)
2. `handle_change_done()` runs gate pipeline (build, test, review) on the branch as-is
3. If gates pass, change enters merge queue
4. `merge_change()` runs `set-merge` which does `git merge branch INTO main`
5. If merge conflicts occur, LLM resolution is attempted on main
6. Post-merge: build check runs on main, smoke tests run on main
7. If post-merge build fails: `build_broken_on_main` flag halts dispatch, `smoke_fix_scoped` tries to fix main

This creates a gap: the branch was tested WITHOUT main's latest changes integrated. When main has diverged, the merged result can fail even though the branch passed all gates. The recovery machinery (smoke_fix_scoped on main, build_broken_on_main) is complex, fragile, and modifies main directly.

## Goals / Non-Goals

**Goals:**
- Main never breaks: only tested, passing code reaches main via fast-forward
- Conflict resolution happens on branch where the agent has full context
- Simplify merger.py by removing post-merge recovery machinery
- Reduce wasted tokens from post-merge fix attempts on main

**Non-Goals:**
- Changing how agents implement features (dispatch, loop, done criteria unchanged)
- Modifying gate logic itself (build, test, review gates work the same)
- Optimizing for the case where main rarely changes (the current happy path is already fast)
- Supporting non-fast-forward merge strategies (squash merge etc. in orchestrator context)

## Decisions

### Decision 1: Integration happens in verifier, not merger

**Choice:** Add `_integrate_main_into_branch()` at the start of `handle_change_done()` in verifier.py, before the gate pipeline.

**Rationale:** The verifier already owns the "change done -> gates -> merge queue" flow. Adding integration as step 0 keeps the pipeline linear. The alternative (doing it in merger.py) would require the merger to re-run gates, duplicating the entire gate pipeline invocation.

**Alternatives considered:**
- Integration in engine.py poll loop: would split the verify flow across two files, harder to reason about
- Integration as a separate "integrator" module: over-engineering for what is essentially one git merge command + retry logic

### Decision 2: ff-only merge via set-merge --ff-only

**Choice:** Add `--ff-only` flag to `bin/set-merge` that does `git merge --ff-only` without any conflict resolution, LLM calls, or conservation checks. Merger.py calls `set-merge <change> --no-push --ff-only` instead of `set-merge <change> --no-push --llm-resolve`.

**Rationale:** Keeps the CLI as the single merge entry point. The ff-only path is trivially simple (one git command), but routing through set-merge ensures hooks, cleanup, and logging remain consistent.

**Alternatives considered:**
- Direct `git merge --ff-only` in merger.py: would bypass set-merge's pre-merge cleanup (runtime files, auto-stash), requiring duplication
- New `set-ff-merge` command: unnecessary complexity, set-merge already handles all merge modes

### Decision 3: Re-integration retry loop lives in merger.py

**Choice:** When `merge_change()` detects ff-only failure, it calls back to verifier for re-integration + re-gating, creating a retry loop. Maximum 3 retries (configurable via `max_ff_retries` directive).

**Rationale:** The merger owns the "advance main" operation. When ff fails, it needs to trigger re-integration (verifier) + re-gating (verifier) + re-ff (merger). This is a natural retry loop in the merger.

**Flow:**
```
handle_change_done():
  _integrate_main_into_branch(wt_path)     # verifier
  gate_pipeline.run()                        # verifier
  -> status = "done", add to merge_queue

merge_change():
  set-merge --ff-only                        # merger
  if ff fails:
    re-integrate main into branch            # merger calls git directly
    set status back to "running"             # merger triggers re-verify
    resume_change()                          # dispatcher
    return MergeResult(success=False, status="running")
  else:
    proceed to archive/cleanup
```

### Decision 4: Remove build_broken_on_main and smoke_fix_scoped dependency

**Choice:** Delete the `build_broken_on_main` flag, the `_retry_broken_main_build_safe()` periodic check in engine.py, the dispatch guard that checks the flag, and the `smoke_fix_scoped` call from the blocking smoke pipeline.

**Rationale:** These exist only to handle post-merge build failures. With integrate-then-verify, the build was already verified on the integrated branch before ff-merge. If the build passes on `branch + main`, it will pass on main after ff-only (they are the same commit).

**Risk:** If a build is environment-dependent (e.g., different node_modules state on main vs branch), the ff-only merge could still result in a broken main. This is an edge case that the dependency install post-merge step already handles.

### Decision 5: New "integrating" status

**Choice:** Add "integrating" to the set of valid change statuses. The transition is: `running` -> `integrating` -> `verifying` -> `done` -> `merged`.

**Rationale:** Provides visibility into the integration phase. Without it, changes would appear "running" during integration, which is misleading. The status is also used by the monitor loop to avoid re-polling changes that are mid-integration.

## Risks / Trade-offs

**[Risk] Increased latency for changes when main is active** -> Gates must re-run if main advances during gating. In a busy orchestration with frequent merges, a change could loop 2-3 times before ff succeeds. Mitigation: the retry limit (default 3) caps the worst case, and each retry only re-runs the fast gates (build is cached if no files changed).

**[Risk] Merge conflicts on branch block the agent** -> If main introduces changes that conflict with the branch, the agent must resolve them. This is actually better than the current state (LLM resolves on main without agent context), but could delay merge if conflicts are complex. Mitigation: the agent has full worktree context and the retry_context prompt explains exactly what to do.

**[Risk] Removing build_broken_on_main removes a safety net** -> If a bug slips through (e.g., race condition not caught by integration), there is no longer a mechanism to halt dispatch. Mitigation: the sentinel and watchdog still detect stuck orchestration, and the monitor's completion check handles all-failed cases.

**[Trade-off] Post-merge smoke tests still run on main** -> We keep the smoke pipeline for now because smoke tests may test integration with external services. Future work could move smoke to the pre-merge branch as well.

## Migration Plan

1. Add `--ff-only` flag to `bin/set-merge` (backward compatible)
2. Add `_integrate_main_into_branch()` to verifier.py (new code path, no changes to existing)
3. Modify `merge_change()` to use ff-only and add retry loop
4. Remove `build_broken_on_main` flag and related engine.py code
5. Remove `smoke_fix_scoped` import from merger.py blocking smoke pipeline
6. Add "integrating" and "integration-failed" to valid status values

Rollback: revert to previous merger.py that uses `--llm-resolve` instead of `--ff-only`. The integration step in verifier.py is harmless (extra merge that is a no-op if branch is up-to-date).

## Open Questions

- Should the re-integration retry count share the existing `merge_retry_count` or have its own counter? Leaning toward a separate `ff_retry_count` to avoid conflating two different failure modes.
- Should smoke tests also move to the pre-merge branch? This is a natural extension but increases scope. Recommend deferring to a follow-up change.
