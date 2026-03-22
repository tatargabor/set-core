# Proposal: sentinel-reset-guard

## Why

The sentinel auto-resets orchestration state whenever it detects a spec hash change — destroying worktrees, branches, and completed agent work. In craftbrew-run8, this caused 3 full resets in one session, each time losing 30-60 min of agent work. The root cause: sentinel stores "unknown" hash on restart, compares to current hash, and always detects "changed."

## What Changes

- **ENHANCE**: `set-sentinel` — before resetting orchestration, write a `reset-pending` marker file and wait for approval instead of auto-resetting
- **ENHANCE**: `set-sentinel` — add `--auto-approve-reset` flag for unattended runs where auto-reset is acceptable
- **ENHANCE**: `set-sentinel` — distinguish "spec actually changed" from "I lost my hash state" (persist hash to disk)

## Capabilities

### Modified Capabilities
- `sentinel-reset`: Guard against accidental state destruction

## Impact

- **Modified files**: `bin/set-sentinel` (reset guard logic, hash persistence)
- **Risk**: Low — additive guard, existing behavior preserved with `--auto-approve-reset`
- **Dependencies**: None
