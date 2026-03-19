## Why

Orphan detection in `wt-status` kills agents immediately on the first detection pass. This causes false positive kills — e.g., when opening a new Claude terminal in Zed, the `is_editor_open()` osascript check can momentarily fail (timing, focus change, System Events latency), causing the existing agent to be killed despite the editor being open. A grace period with a counter will eliminate transient false positives.

## What Changes

- Add a grace period mechanism to `cleanup_orphan_agents()` in `bin/wt-status`: agents must be detected as orphan **3 consecutive times** AND **at least 15 seconds** must have elapsed since first orphan detection before being killed
- Track orphan detection state per-PID using lightweight marker files in `.set-core/orphan-detect/`
- Reset tracking when an agent is no longer detected as orphan (editor reopened, TTY restored, etc.)
- Clean up stale marker files for PIDs that no longer exist

## Capabilities

### New Capabilities
- `orphan-grace-period`: Grace period and counter mechanism for orphan agent cleanup to prevent false positive kills

### Modified Capabilities

## Impact

- `bin/wt-status`: `cleanup_orphan_agents()` function modified to track state and delay kills
- `.set-core/orphan-detect/` directory created per-worktree for tracking state
- No GUI changes needed — orphan display and context menu kill remain unchanged
- No breaking changes — orphans are still auto-killed, just with a safe delay
