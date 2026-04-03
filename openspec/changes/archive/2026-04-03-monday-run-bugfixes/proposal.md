## Why

Production orchestration runs exposed 4 bugs in the merge/gate pipeline that caused changes to get stuck in integration-failed state, requiring manual sentinel intervention. These are framework-level issues that recur across projects unless fixed.

## What Changes

- **vitest no-test-files gate skip**: When `pnpm test` (vitest) exits with code 1 because there are no test files, the integration gate retries 15+ times without any code change. The gate should detect "no test files found" and skip instead of failing.
- **total_merge_attempts TypeError**: `extras.get("total_merge_attempts")` can return `None` (not 0), causing `None + 1` TypeError in the merge retry path. Need defensive int coercion.
- **merge-blocked auto-recovery**: When a change is merge-blocked due to a blocking issue that later gets resolved, the orchestrator doesn't automatically retry. The engine poll should detect resolved blockers and re-queue.
- **pre-merge dependency validation**: Changes can enter the merge queue before all transitive dependencies are on main. The merge gate should validate deps are merged before attempting integration gates.

## Capabilities

### New Capabilities
_(none)_

### Modified Capabilities
- `integration-gate-redispatch` — Add no-test-files detection to skip test gate
- `merge-worktree` — Fix TypeError + add dep validation before merge

## Impact

- **lib/set_orch/merger.py**: TypeError fix, dep validation, no-test detection
- **lib/set_orch/engine.py**: Auto-recovery for resolved blockers in poll loop
- **modules/web/set_project_web/project_type.py**: Possible vitest-specific detection helper
