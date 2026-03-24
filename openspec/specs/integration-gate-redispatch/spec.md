# Spec: Integration Gate Redispatch

## Requirements

### REQ-1: E2E failure triggers agent redispatch
When the integration e2e gate fails for a change, the engine MUST redispatch the agent to the worktree with the e2e error context, instead of immediately marking merge-blocked.

### REQ-2: Error context includes test output
The redispatch retry_context MUST include:
- The failed test names
- The error output (truncated to last 2000 chars)
- The original change scope
- Instruction to fix the e2e failures

### REQ-3: Retry counter limits redispatch
An `integration_e2e_retry_count` counter tracks redispatch attempts. Maximum 2 retries (matching `max_verify_retries`). After exhausting retries → `merge-blocked` (existing flow).

### REQ-4: Agent works in existing worktree
The redispatch MUST use the existing worktree (not create a new one). The agent fixes the code in-place, commits, and the change returns to `done` status for re-verification.

### REQ-5: Flow returns to normal merge pipeline
After agent fix: done → merge queue → integration gates (build + test + e2e) → merge. The full gate pipeline runs again, not just e2e.

## Acceptance Criteria

- [ ] Integration e2e failure redispatches agent with error context on first failure
- [ ] Agent receives test failure output in retry_context
- [ ] After 2 failed redispatch attempts, change becomes merge-blocked (existing behavior)
- [ ] Redispatch uses existing worktree, not new one
- [ ] After agent fix, change goes through full integration gate pipeline again
