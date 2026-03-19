## Why

MiniShop E2E Run #4 completed 7/7 changes in 2h wall clock but only 1h18m active time — 42 minutes wasted on watchdog kill/resume cycles. Code analysis revealed a bug: hash loop detection kills healthy agents (PID alive) because it lacks the PID-alive guard that timeout detection already has. Additional bottlenecks: sequential dispatch ignores complexity (large changes should start first), and worktrees drift behind main between merges causing avoidable gate retries.

## What Changes

- **Fix watchdog false-positive kills** — add PID-alive guard to hash loop detection (`watchdog.sh:116`), matching the existing timeout guard at line 122-128. This is the root cause of the 42 min idle time.
- **Complexity-aware dispatch ordering** — within the same topological level, dispatch larger (L) changes before smaller (S/M) ones. Reduces tail latency by starting bottleneck changes earlier.
- **Eager worktree sync after merge** — after each successful merge, sync all running worktrees with main. Prevents "stale main" gate failures that require a full retry cycle.
- **Increase default max_parallel to 3** — 2 is too conservative for 7-change plans. 3 allows better pipeline utilization without excessive merge conflict risk.

## Capabilities

### New Capabilities
- `watchdog-pid-guard`: PID-alive guard on hash loop detection to prevent false-positive agent kills
- `complexity-dispatch-order`: Dispatch larger changes first within the same dependency level
- `post-merge-sync`: Sync running worktrees with main after each successful merge
- `max-parallel-default`: Increase default max_parallel from 2 to 3

### Modified Capabilities

## Impact

- `lib/orchestration/watchdog.sh` — hash loop detection guard (3 lines)
- `lib/orchestration/dispatcher.sh` — dispatch ordering in `dispatch_ready_changes()`
- `lib/orchestration/merger.sh` — post-merge sync loop
- `lib/orchestration/state.sh` — topological sort complexity weighting
- `bin/set-orchestrate` — DEFAULT_MAX_PARALLEL constant
