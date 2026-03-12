## Why

CraftBrew E2E orchestration run (2026-03-10) revealed three bugs that cause the orchestrator to hang, report incorrect metrics, or block replan cycles. All three are small, safe fixes (1-10 lines each) with no architectural changes needed.

## What Changes

- **Fix dependency deadlock (#16)**: Move `cascade_failed_deps()` call before `dispatch_ready_changes()` in the monitor loop so failed dependencies are cascaded before dispatch attempts, preventing permanent deadlock when a change fails.
- **Fix active_seconds timer (#17)**: Add "verifying" status to `any_loop_active()` check so the timer increments during verify phases, fixing stuck timer and ensuring time_limit enforcement works correctly.
- **Fix digest replan failure (#21)**: Add hash-based skip logic so re-digest is skipped when spec files haven't changed, preventing JSON parse failures that block replan cycles.

## Capabilities

### New Capabilities

_(none — all fixes modify existing orchestrator internals)_

### Modified Capabilities

- `orchestration-engine`: Fix cascade ordering in monitor loop (deadlock prevention)
- `verify-gate`: Fix timer increment during verify phase
- `spec-digest`: Add hash-based skip for unchanged specs during replan

## Impact

- `lib/orchestration/monitor.sh` — cascade call ordering
- `lib/orchestration/utils.sh` — any_loop_active status check
- `lib/orchestration/planner.sh` — digest freshness skip logic
- No API changes, no config changes, no new dependencies
