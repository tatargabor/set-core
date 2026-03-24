# Proposal: Integration E2E Redispatch

## Why

When the integration e2e gate fails during merge, the change gets stuck as `merge-blocked` with no recovery path. The engine retries the same merge 3 times (same bug → same failure), then marks `integration-failed`. The agent never gets a chance to fix the code. This is inconsistent with verify-failed and build-failed flows which both redispatch the agent with error context.

Found in minishop-run2: admin-products had a "use server" + Zod export bug. The verify e2e didn't catch it (or wasn't run), but the integration e2e did. The change got merge-blocked → integration-failed with no fix attempt.

## What Changes

- Integration e2e failure triggers agent redispatch with e2e error context (same pattern as verify-failed retry)
- The agent receives the failed test output and can fix the code in its worktree
- After fix, the change goes through done → merge queue → integration gates again
- A retry counter limits redispatch attempts (max 2, matching verify retry limit)

## Capabilities

### New Capabilities
- `integration-gate-redispatch` — redispatch agent on integration gate e2e failure with error context

### Modified Capabilities
_(none — this extends the existing merge pipeline, no spec-level behavior changes)_

## Impact

- `lib/set_orch/merger.py` — `_run_integration_gates()` e2e fail path: instead of immediate merge-blocked, set retry context and redispatch
- `lib/set_orch/engine.py` — monitor loop handles new `integration-e2e-failed` status (or reuses existing verify-failed flow)
- `lib/set_orch/dispatcher.py` — `resume_change()` already exists, just needs to be called from the new path
