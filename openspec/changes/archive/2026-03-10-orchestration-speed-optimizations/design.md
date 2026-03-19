## Context

The orchestrator poll loop runs every 15s. Each cycle: poll active changes, watchdog checks, dispatch ready changes, retry merges, check completion. Changes flow: pending → dispatched → running → done → verifying → merged. Gates execute sequentially: test → build → E2E → scope → review → verify → merge.

Run #4 stats: 2h wall, 1h18m active, 7 watchdog kills, 8 resumes. The 42 min idle is dominated by kill/resume cycles on healthy agents.

## Goals / Non-Goals

**Goals:**
- Eliminate false-positive watchdog kills (A1)
- Start bottleneck changes earlier via complexity-aware dispatch (A6)
- Prevent stale-main gate retries via post-merge sync (A5)
- Better pipeline utilization with max_parallel=3 (P2)

**Non-Goals:**
- Changing the gate pipeline (parallelizing test+build)
- Model routing changes (Sonnet for smaller changes — too risky per analysis)
- Changing the watchdog threshold (reducing it would make kills worse)
- Planner dependency graph changes (that's a planner prompt concern)

## Decisions

**D1: PID-alive guard on hash loop detection**
- Add the same `kill -0 "$ralph_pid"` check that timeout detection uses (watchdog.sh:122-128) before the hash loop escalation (watchdog.sh:116)
- If PID is alive AND hash is looping → log warning but do NOT escalate
- Rationale: A healthy PID with identical hashes means the agent is working on a long operation where tokens haven't been polled yet. The 15s poll interval creates a real window where 5 consecutive identical hashes are normal.

**D2: Complexity-aware dispatch ordering**
- Modify `dispatch_ready_changes()` to sort pending, dependency-satisfied changes by complexity before dispatching
- Sort order: L > M > S (larger first)
- Implementation: After filtering pending + deps_satisfied, sort by complexity from state, then dispatch in that order
- Rationale: Larger changes are the critical path. Starting them first reduces tail latency. In Run #4, admin-auth (L, 41 min) started at the same time as cart (M, 20 min) — if it had started 14 min earlier (when products-page finished), it would have finished 14 min earlier.

**D3: Post-merge worktree sync**
- After `merge_change()` succeeds, iterate all running changes and call `sync_worktree_with_main` for each
- The sync function already handles the "already up to date" case (returns immediately)
- The sync function already handles conflicts gracefully (auto-resolves generated files, aborts on real conflicts)
- Rationale: Without this, running worktrees fall behind main after each merge. When they complete and enter gates, the build gate may fail due to stale dependencies, causing a retry cycle (~5-10 min + tokens wasted).

**D4: Default max_parallel 3**
- Change `DEFAULT_MAX_PARALLEL=2` to `DEFAULT_MAX_PARALLEL=3` in `bin/set-orchestrate`
- Still overridable via CLI `--max-parallel` and orchestration.yaml
- Rationale: With 7-change plans, max_parallel=2 creates unnecessary serialization. The merge queue is already flock-protected, so 3 concurrent branches are safe.

## Risks / Trade-offs

- [Risk] PID-alive guard may mask genuine loop-stuck scenarios where PID is alive but agent is infinitely looping → Mitigation: log a warning on every poll so it's visible in the TUI; the timeout check (600s) still triggers escalation for truly stuck agents since it also checks PID
- [Risk] max_parallel=3 increases merge conflict probability → Mitigation: the post-merge sync (D3) actively reduces divergence; merge queue remains sequential with flock
- [Risk] Post-merge sync may cause transient git conflicts in running worktrees → Mitigation: sync_worktree_with_main already handles conflicts (auto-resolve for generated files, skip on real conflicts). Worst case: sync fails silently and the change retries at gate time as before.
- [Trade-off] Complexity dispatch ordering requires reading change complexity from state for each dispatch candidate — negligible overhead (1 jq call per pending change)
