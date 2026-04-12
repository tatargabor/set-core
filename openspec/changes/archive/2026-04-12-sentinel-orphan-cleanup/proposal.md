# Proposal: sentinel-orphan-cleanup

## Why

When the sentinel or orchestrator restarts (context limit, crash, manual restart), orphaned resources accumulate: worktrees without state entries, dead ralph_pid references causing dashboard animations to freeze, and `current_step` stuck at intermediate values. In craftbrew-run22, `checkout-flow-2` was an orphaned worktree taking disk space, and `checkout-flow` had `step=integrating` with a dead PID — the dashboard M gate badge animated indefinitely until manually fixed. These are not one-off issues: every sentinel restart in a long run leaves detritus.

## What Changes

- **NEW**: `_cleanup_orphans()` function in `lib/set_orch/engine.py` — runs at orchestrator startup, fixes stale state and removes orphaned worktrees
- **MODIFIED**: `monitor_loop()` in `engine.py` — call `_cleanup_orphans()` before entering the poll loop
- **MODIFIED**: `health_check()` in `supervisor.py` — detect stuck steps in periodic health checks

## Capabilities

### New Capabilities
- `orphan-cleanup` — Detect and clean orphaned resources on orchestrator startup

### Modified Capabilities
- (none — this extends the existing monitor startup sequence)

## Impact

- `lib/set_orch/engine.py` — new `_cleanup_orphans()` + call from `monitor_loop()`
- `lib/set_orch/manager/supervisor.py` — optional stuck-step detection in health_check
- No new dependencies, no schema changes
