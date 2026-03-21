## IN SCOPE
- Move e2e, lint, smoke gate executors from core to modules/web
- WebProjectType.register_gates() implementation
- Gate executor context adaptation (GateContext instead of per-gate params)

## OUT OF SCOPE
- Changing gate behavior (exact same logic, just moved)
- Adding new web gates
- Python module gates (future work)

### Requirement: E2E gate executor shall live in web module
The `_execute_e2e_gate` function SHALL move from `lib/set_orch/verifier.py` to `modules/web/set_project_web/gates.py`. It SHALL receive a GateContext and return a GateResult. All existing logic (playwright config parsing, baseline comparison, screenshot collection, runtime error detection) SHALL be preserved.

#### Scenario: E2E gate works from web module
- **GIVEN** WebProjectType is loaded
- **AND** change_type is "feature"
- **WHEN** the e2e gate executes
- **THEN** behavior SHALL be identical to the current _execute_e2e_gate

### Requirement: Lint gate executor shall live in web module
The `_execute_lint_gate` function SHALL move from `lib/set_orch/verifier.py` to `modules/web/set_project_web/gates.py`. Pattern loading from profile + project-knowledge.yaml SHALL be preserved.

### Requirement: Smoke gate executor shall live in web module
Post-merge smoke test execution logic SHALL move from `lib/set_orch/merger.py` to `modules/web/set_project_web/gates.py`. The merger SHALL call profile-registered post-merge gates instead of hardcoded smoke functions.

### Requirement: Core verifier shall not contain domain-specific executors
After migration, `lib/set_orch/verifier.py` SHALL NOT contain `_execute_e2e_gate`, `_execute_lint_gate`, `_auto_detect_e2e_command`, or any Playwright/package.json references. These SHALL only exist in `modules/web/`.
