# Proposal: gate-e2e-autodetect

**Series: programmatic-gate-enforcement (1/4)**

## Why

E2E tests silently skip for feature changes in web projects because the e2e_command resolution chain breaks at multiple points. The profile loader fails to load project-type plugins when entry_points registration is missing (common with editable installs), falling back to NullProfile which has no auto-detect methods. Even when the worktree has a playwright.config.ts and package.json with "test:e2e", the E2E gate returns "skipped" instead of detecting and running the tests.

This has been confirmed across multiple E2E orchestration runs: feature changes (including bugfix changes that specifically fix E2E failures) merge without any E2E validation. The gate profile says e2e="run" for feature changes, but the empty e2e_command makes it skip silently.

## What Changes

- **Profile loader resilience**: Add direct import fallback when entry_points lookup returns empty — if project-type.yaml says type=web but entry_points has no registration, try `importlib.import_module("set_project_web")` directly
- **E2E command auto-detect**: When e2e_command is empty but playwright.config.ts exists in the worktree, auto-detect from package.json scripts (test:e2e, e2e, playwright) or fall back to "npx playwright test"
- **Mandatory E2E for web features**: When the project profile is web-type AND change_type=feature AND playwright config exists, the E2E gate MUST fail (not skip) if no e2e tests are found or if auto-detect fails
- **NullProfile.detect_e2e_command**: Add method to NullProfile interface so all profiles can provide e2e command detection

## Capabilities

### New Capabilities
- `e2e-autodetect`: Auto-detect e2e_command from playwright config and package.json scripts when not explicitly configured

### Modified Capabilities
- `profile-loader`: Direct import fallback for entry_points failure
- `verify-gate`: E2E gate uses auto-detected command, fails instead of skipping for web feature changes

## Impact

- **Files modified**: `lib/set_orch/profile_loader.py` (fallback import), `lib/set_orch/verifier.py` (_execute_e2e_gate auto-detect), `lib/set_orch/gate_profiles.py` (NullProfile interface)
- **Risk**: Low — fallback paths only activate when current path already fails (NullProfile)
- **Tests**: New unit tests for profile loader fallback and e2e auto-detect; existing gate_profiles tests must pass
