## Why

When the orchestrator is interrupted (SIGINT, crash, time limit), running changes get their state.json status set to `"stopped"`. On restart, the monitor loop only polls `running` and `verifying` changes, and `dispatch_ready_changes` only dispatches `pending` changes. The `stopped` status falls through every check — these changes are permanently stuck until manual intervention.

This was observed in production: `test-scenario-schema` stayed `stopped` indefinitely while the orchestrator ran, requiring manual state reset.

## What Changes

Add auto-resume logic for `stopped` changes on orchestrator restart. When the orchestrator resumes from a `stopped` state, it should detect changes with `stopped` status and resume them (re-dispatch to their existing worktree).

## Capabilities

### Modified Capabilities
- `orchestration-engine`: Add stopped-change auto-resume on orchestrator restart

## Impact

- `bin/wt-orchestrate`: resume path in `cmd_start()` (around line 2136-2139), and potentially the poll loop filter (line 3129)
