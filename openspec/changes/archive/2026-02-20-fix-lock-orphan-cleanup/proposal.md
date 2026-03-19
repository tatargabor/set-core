## Why

The `run_with_lock()` function in `set-memory` uses `mkdir`-based locking but has a bug: when the lock acquisition times out, the function returns without cleaning up any previously orphaned lock directory. Since the `trap` is only set AFTER successful acquisition, a crash or kill during the locked section leaves an orphaned `/tmp/set-memory-<project>.lock` directory that blocks ALL subsequent write operations (forget, cleanup, dedup, export) permanently until manual removal.

## What Changes

- Add stale lock detection to `run_with_lock()` — if the lock directory exists but is older than N seconds, auto-remove it before retrying
- Add explicit cleanup on timeout path so the function doesn't silently fail
- Ensure the MCP server surfaces lock errors clearly instead of returning empty/default JSON

## Capabilities

### New Capabilities
- `stale-lock-recovery`: Automatic detection and recovery from orphaned/stale lock directories in `run_with_lock()`

### Modified Capabilities
- `memory-concurrency`: The lock timeout path now includes stale-lock detection and self-healing instead of silent failure

## Impact

- `bin/set-memory`: `run_with_lock()` function (lines 211-234)
- All MCP memory tools that use `run_with_lock` (forget, cleanup, dedup, export, etc.)
- No API changes, no breaking changes — purely defensive improvement
