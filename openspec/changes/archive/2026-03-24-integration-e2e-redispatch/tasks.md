# Tasks: Integration E2E Redispatch

## 1. merger.py — e2e fail redispatch path

- [x] 1.1 In `_run_integration_gates()`, after e2e fail + `gc.is_blocking("e2e")`: check `integration_e2e_retry_count` from extras
- [x] 1.2 If retry_count < max (2): save e2e output to `extras["integration_e2e_output"]`, build retry_context with failed test names + error output + original scope
- [x] 1.3 Set status to `integration-e2e-failed` (new status), remove from merge queue, return False
- [x] 1.4 If retry_count >= max: fall through to existing merge-blocked flow (no change)
- [x] 1.5 Increment `integration_e2e_retry_count` in extras

## 2. engine.py — monitor loop handler

- [x] 2.1 In `_recover_verify_failed()` or new `_recover_integration_e2e_failed()`: detect status `integration-e2e-failed`
- [x] 2.2 Check worktree exists — if not, fall back to merge-blocked
- [x] 2.3 Build retry_context from `extras["integration_e2e_output"]` if not already set: "Integration e2e tests failed after merge. Fix the failing tests:\n\n{output}\n\nOriginal scope: {scope}"
- [x] 2.4 Call `resume_change()` with the retry_context — agent runs in existing worktree
- [x] 2.5 After agent completes (status → done), the normal merge queue flow picks it up again

## 3. Status tracking

- [x] 3.1 Add `integration-e2e-failed` to any status validation/enum if exists — no enum/validation found, status is free-form string
- [x] 3.2 Ensure the dashboard/API handles the new status (renders correctly) — dashboard renders status strings dynamically, no hardcoded list
