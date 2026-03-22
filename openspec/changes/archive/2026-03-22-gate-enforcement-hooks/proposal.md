# Proposal: gate-enforcement-hooks

**Series: programmatic-gate-enforcement (4/4)**

## Why

The orchestration pipeline has lifecycle hooks (hook_pre_dispatch, hook_post_verify, hook_pre_merge, hook_post_merge) but they are only configurable as shell scripts in orchestration.yaml directives. Project-type plugins cannot programmatically inject hooks, and there is no framework for composing multiple hook sources (directives + profile + project-knowledge.yaml).

Additionally, post-verify screenshot archival and pre-dispatch environment validation currently rely on LLM compliance (agent instructions) rather than programmatic enforcement. Web projects should automatically validate Playwright availability at dispatch time and archive E2E screenshots after verification.

## What Changes

- **Profile hook interface**: Add `get_pre_dispatch_checks()` and `get_post_verify_hooks()` methods to the profile interface. These return callables that the engine invokes at the appropriate lifecycle points.
- **Pre-dispatch validation**: For web profiles, validate that playwright config exists and node_modules includes playwright when dispatching feature changes. Fail dispatch (not silent skip) if validation fails.
- **Post-verify screenshot archival**: After E2E gate passes, automatically archive screenshots to the run's screenshot directory. Currently done inline in _execute_e2e_gate but should be a composable hook.
- **Hook composition**: Engine combines directive hooks (shell scripts) with profile hooks (callables) at each lifecycle point. Both run; directive hooks run first.

## Capabilities

### New Capabilities
- `profile-hooks`: Profile plugins can register pre-dispatch checks and post-verify hooks

### Modified Capabilities
- `verify-gate`: Post-verify hooks invoked after gate pipeline completes
- `dispatch`: Pre-dispatch profile checks invoked before worktree creation

## Impact

- **Files modified**: `lib/set_orch/profile_loader.py` (NullProfile hook methods), `lib/set_orch/engine.py` (hook composition at dispatch/verify), `lib/set_orch/dispatcher.py` (pre-dispatch profile checks)
- **Risk**: Medium — modifies dispatch and verify paths. Profile hooks are opt-in (NullProfile returns empty lists).
- **Tests**: New unit tests for hook composition; existing dispatch/verify tests must pass
