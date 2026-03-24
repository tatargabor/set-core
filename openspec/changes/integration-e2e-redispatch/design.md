# Design: Integration E2E Redispatch

## Approach

Reuse the existing verify-failed → retry pattern. The code paths are nearly identical:

```
VERIFY-FAILED (existing):
  verifier.py → status="verify-failed" + retry_context
  engine.py _recover_verify_failed → resume_change()
  dispatcher.py resume_change() → agent runs in worktree

INTEGRATION E2E FAIL (new):
  merger.py _run_integration_gates → e2e fail
  → status="integration-e2e-failed" + retry_context + save e2e output
  engine.py monitor_loop → detect "integration-e2e-failed"
  → resume_change() with retry_context
  dispatcher.py resume_change() → agent runs in worktree
  → agent fixes → done → merge queue again
```

## Key Decisions

### D1: New status value `integration-e2e-failed`
Use a distinct status rather than reusing `verify-failed` to avoid confusion in logs/UI. The monitor loop handles it the same way but the status makes it clear this is an integration-phase failure.

### D2: E2e output capture in extras
Store the e2e test output in `change.extras["integration_e2e_output"]` so the retry_context can be built from it. Same pattern as `build_output` for build failures.

### D3: Counter in extras
`integration_e2e_retry_count` in extras, checked in `_run_integration_gates()`. If >= max (2) → fall through to existing merge-blocked flow.

### D4: Worktree must exist
The redispatch needs the worktree to still exist. The `cleanup_worktree` only runs after successful merge, so the worktree should be intact. If not found → fall through to merge-blocked.

## Files to Modify

| File | Change |
|------|--------|
| `lib/set_orch/merger.py` | `_run_integration_gates()` — e2e fail path: check retry counter, save output, set status |
| `lib/set_orch/engine.py` | `monitor_loop` — add `integration-e2e-failed` handler that calls `resume_change()` |
| `lib/set_orch/dispatcher.py` | No changes — `resume_change()` already handles retry_context |
