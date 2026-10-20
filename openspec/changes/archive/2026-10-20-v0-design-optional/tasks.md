## 1. Core ABC and Config

- [x] 1.1 Add `has_design_pipeline(project_path, directives=None)` to `ProjectType` ABC in `lib/set_orch/profile_types.py` — base returns `False` [REQ: has_design_pipeline-method-on-projecttype-abc]
- [x] 1.2 Add `"design_pipeline": "auto"` to `DIRECTIVE_DEFAULTS` in `lib/set_orch/config.py` [REQ: design_pipeline-directive]

## 2. Web Module Implementation

- [x] 2.1 Override `has_design_pipeline()` in `WebProjectType` — NOT NEEDED: base ABC implementation already delegates to `detect_design_source()` which WebProjectType overrides. Inheritance handles this correctly. [REQ: has_design_pipeline-method-on-projecttype-abc]
- [x] 2.2 Filter design-fidelity gate at verifier pipeline registration (`verifier.py:4222`) using `profile.has_design_pipeline()`. No ABC signature change needed — verifier already has profile, project_path, and directives in scope. [REQ: conditional-gate-registration]

## 3. Dispatcher Integration

- [x] 3.1 Replace inline `detect_design_source() != "none"` check in `dispatcher.py:3080` with `profile.has_design_pipeline(project_path, directives)`. Also fixed null-safety for _design_profile and a variable name collision. [REQ: has_design_pipeline-method-on-projecttype-abc]

## 4. Tests

- [x] 4.1 Test `has_design_pipeline()` base class returns False [REQ: has_design_pipeline-method-on-projecttype-abc]
- [x] 4.2 Test `WebProjectType.has_design_pipeline()` returns True when v0-export exists, False when absent [REQ: has_design_pipeline-method-on-projecttype-abc]
- [x] 4.3 Test directive `"none"` overrides auto-detection (v0-export exists but directive says none → False) [REQ: design_pipeline-directive]
- [x] 4.4 Test `register_gates()` includes design-fidelity regardless (filtering at verifier level) [REQ: conditional-gate-registration]
- [x] 4.5 Test `register_gates()` includes design-fidelity when `has_design_pipeline()` returns True [REQ: conditional-gate-registration]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN verifier registers profile gates AND `has_design_pipeline()` returns True THEN design-fidelity is registered in pipeline [REQ: conditional-gate-registration, scenario: web-project-with-v0-export-includes-gate]
- [x] AC-2: WHEN verifier registers profile gates AND `has_design_pipeline()` returns False THEN design-fidelity is skipped [REQ: conditional-gate-registration, scenario: web-project-without-v0-export-excludes-gate]
- [x] AC-3: WHEN orchestration directives contain `design_pipeline: "none"` AND `v0-export/` exists THEN `has_design_pipeline()` SHALL return False [REQ: conditional-gate-registration, scenario: design_pipeline-directive-set-to-none-excludes-gate]
- [x] AC-4: WHEN `execute_design_fidelity_gate()` is called AND no scaffold.yaml/v0-export in worktree THEN status SHALL be "skipped" with output "skipped-no-design-source" [REQ: runtime-skip-preserved-as-defense-in-depth, scenario: gate-runs-but-no-v0-source-at-runtime]
- [x] AC-5: WHEN no `design_pipeline` directive exists THEN the effective value SHALL be "auto" [REQ: design_pipeline-directive, scenario: default-value-is-auto]
- [x] AC-6: WHEN `design_pipeline: "none"` THEN `has_design_pipeline()` SHALL return False regardless of v0-export presence [REQ: design_pipeline-directive, scenario: explicit-none-disables-design-pipeline]
- [x] AC-7: WHEN `ProjectType.has_design_pipeline()` is called on the base ABC THEN it SHALL return False [REQ: has_design_pipeline-method-on-projecttype-abc, scenario: base-class-returns-false]
