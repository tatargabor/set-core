## IN SCOPE
- Move e2e, lint gate executors from core to modules/web
- WebProjectType.register_gates() implementation
- Move merge_i18n_sidecars to web module post_merge_hooks
- Delete dead smoke pipeline code from merger.py

## OUT OF SCOPE
- Changing gate behavior (exact same logic, just moved)
- Adding new web gates
- Python module gates (future work)
- GateContext dataclass (separate change)

### Requirement: E2E gate executor shall live in web module
The `_execute_e2e_gate` function SHALL move from `lib/set_orch/verifier.py` to `modules/web/set_project_web/gates.py`. It SHALL keep its current parameter signature (no GateContext yet) and return a GateResult. All existing logic (playwright config parsing, baseline comparison, screenshot collection, runtime error detection) SHALL be preserved.

#### Scenario: E2E gate works from web module
- **GIVEN** WebProjectType is loaded
- **AND** change_type is "feature"
- **WHEN** the e2e gate executes
- **THEN** behavior SHALL be identical to the current _execute_e2e_gate

### Requirement: Lint gate executor shall live in web module
The `_execute_lint_gate` function SHALL move from `lib/set_orch/verifier.py` to `modules/web/set_project_web/gates.py`. Pattern loading from profile + project-knowledge.yaml SHALL be preserved.

### Requirement: Dead smoke pipeline shall be removed
The dead code in `merger.py` — `_run_smoke_pipeline`, `_blocking_smoke_pipeline`, `_nonblocking_smoke_pipeline`, `_collect_smoke_screenshots` — SHALL be deleted. These functions have no callers since the ff-only merge strategy was adopted.

### Requirement: Web post-merge hooks shall live in web module
`merge_i18n_sidecars()` SHALL move from `lib/set_orch/merger.py` to `modules/web/set_project_web/post_merge.py`. It SHALL be called via `WebProjectType.post_merge_hooks()`. The merger ff-success path SHALL call `profile.post_merge_hooks()` instead of hardcoding `merge_i18n_sidecars()`.

### Requirement: Core verifier shall not contain domain-specific executors
After migration, `lib/set_orch/verifier.py` SHALL NOT contain `_execute_e2e_gate`, `_execute_lint_gate`, `_auto_detect_e2e_command`, or any Playwright/package.json references. These SHALL only exist in `modules/web/`.
