# Design: sentinel-reset-guard

## Context

The sentinel (`bin/set-sentinel`) monitors orchestration runs. When it detects a spec hash change, it calls `_reset_orchestration()` which archives the current state, deletes worktrees/branches, and starts fresh. This is correct when the spec actually changed, but false-positives when the sentinel simply lost its hash state (restart, crash recovery).

## Decisions

### D1: Persist spec hash to disk
Store the last-seen spec hash in `sentinel-state.json` alongside `sentinel.lock`. On restart, read the persisted hash instead of defaulting to "unknown."

### D2: Reset requires approval file
Before resetting, sentinel writes `.sentinel-reset-pending` with the reason and waits. The operator (or sentinel CLI) creates `.sentinel-approve-reset` to proceed. Timeout: 5 minutes, then continue without reset (preserve state).

### D3: `--auto-approve-reset` flag
For CI/unattended runs, this flag skips the approval gate and auto-resets (current behavior). Default: approval required.

### D4: Distinguish hash-unknown from hash-changed
If persisted hash is missing (first run ever), auto-approve. If persisted hash exists and differs from current → request approval. If persisted hash matches → no reset needed.

## Files

| File | Change |
|------|--------|
| `bin/set-sentinel` | Hash persistence, reset guard, approval gate, --auto-approve-reset flag |
| Tests | Sentinel reset guard unit tests |
