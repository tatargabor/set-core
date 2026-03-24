# Proposal: E2E Coverage Enforcement

## Why

The planning rules tell agents to write e2e tests for every feature, but there's no programmatic enforcement. In minishop-run2, the admin-products agent wrote e2e tests that only verified page loads — not actual CRUD operations. The "use server" bug went undetected because no test actually submitted a form. The e2e gate passed because the tests it ran were trivially passing.

The existing `test_files` gate checks that `*.spec.*` files exist in the diff, but doesn't verify they contain meaningful assertions matching the change scope.

## What Changes

- **Decompose phase**: Web profile `decompose_hints()` injects explicit e2e requirements per change based on scope keywords (CRUD, forms, auth, etc.)
- **Verify phase**: New `e2e_coverage` gate scans spec.ts files in the diff for assertion patterns matching scope requirements
- **Review phase**: Coverage gaps are injected into the review prompt so the reviewer flags missing tests
- **Web template**: Updated planning_rules.txt with CRUD test checklist and layout consistency rule

## Capabilities

### New Capabilities
- `e2e-coverage-check` — programmatic e2e test coverage verification based on scope analysis

### Modified Capabilities
_(none)_

## Impact

- `modules/web/set_project_web/project_type.py` — `decompose_hints()` extended with e2e requirements
- `modules/web/set_project_web/planning_rules.txt` — CRUD test checklist added
- `lib/set_orch/verifier.py` — new `_execute_e2e_coverage_gate()`
- `lib/set_orch/templates.py` — review prompt includes coverage gap report
- `modules/web/set_project_web/templates/spa/rules/` — layout consistency rule
