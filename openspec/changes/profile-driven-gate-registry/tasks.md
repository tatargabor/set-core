## 1. GateDefinition and GateContext dataclasses

- [ ] 1.1 Add `GateDefinition` dataclass to `lib/set_orch/gate_runner.py`: name, executor, position, phase, defaults, own_retry_counter, extra_retries [REQ: gates-shall-be-declared-via-gatedefinition]
- [ ] 1.2 Add `GateContext` dataclass to `lib/set_orch/gate_runner.py`: change_name, change, wt_path, profile, state_file, gc, verify_retry_count, event_bus [REQ: gates-shall-be-declared-via-gatedefinition]
- [ ] 1.3 Add `register_gates() -> list[GateDefinition]` to ProjectType ABC in `lib/set_orch/profile_types.py` returning empty list [REQ: profiles-shall-register-domain-specific-gates]
- [ ] 1.4 Add `_resolve_gate_order(universal: list, profile: list) -> list` helper that merges and sorts by position hints [REQ: pipeline-shall-register-gates-from-registry]

## 2. Dynamic GateConfig

- [ ] 2.1 Refactor `GateConfig` in `gate_profiles.py` from fixed-field dataclass to dict-based class with `_gates: dict[str, str]` [REQ: gateconfig-shall-support-arbitrary-gate-names]
- [ ] 2.2 Preserve `should_run()`, `is_blocking()`, `is_warn_only()` using dict lookup with "run" default [REQ: gateconfig-shall-support-arbitrary-gate-names]
- [ ] 2.3 Keep `test_files_required`, `max_retries`, `review_model`, `review_extra_retries` as direct attributes (not in gates dict) [REQ: gateconfig-shall-support-arbitrary-gate-names]
- [ ] 2.4 Define `UNIVERSAL_DEFAULTS`: per change_type defaults for universal gates only (replace the universal parts of BUILTIN_GATE_PROFILES) [REQ: resolve-gateconfig-shall-merge-universal-and-profile]
- [ ] 2.5 Refactor `resolve_gate_config()`: universal defaults → profile gate defaults → gate_overrides → per-change → directives [REQ: resolve-gateconfig-shall-merge-universal-and-profile]
- [ ] 2.6 Remove `BUILTIN_GATE_PROFILES` dict (replaced by UNIVERSAL_DEFAULTS + profile.register_gates defaults) [REQ: resolve-gateconfig-shall-merge-universal-and-profile]

## 3. Universal gate definitions in core

- [ ] 3.1 Create `UNIVERSAL_GATES` list in `lib/set_orch/verifier.py` with GateDefinitions for: build, test, scope_check, test_files, review, rules, spec_verify [REQ: gates-shall-be-declared-via-gatedefinition]
- [ ] 3.2 Adapt universal gate executors to accept `GateContext` instead of individual params (build, test, scope, test_files, review, rules, spec_verify) [REQ: gates-shall-be-declared-via-gatedefinition]

## 4. Move web-specific gate executors to modules/web

- [ ] 4.1 Create `modules/web/set_project_web/gates.py` with `execute_e2e_gate(ctx: GateContext) -> GateResult` — move from verifier.py, preserve all logic [REQ: e2e-gate-executor-shall-live-in-web-module]
- [ ] 4.2 Move `_execute_lint_gate` to `modules/web/set_project_web/gates.py` as `execute_lint_gate(ctx) -> GateResult` [REQ: lint-gate-executor-shall-live-in-web-module]
- [ ] 4.3 Move `_parse_playwright_config`, `_count_e2e_tests`, `_check_e2e_runtime_errors`, `_get_or_create_e2e_baseline` helpers to `modules/web/set_project_web/gates.py` [REQ: e2e-gate-executor-shall-live-in-web-module]
- [ ] 4.4 Move `_load_forbidden_patterns`, `_extract_added_lines` to `modules/web/set_project_web/gates.py` [REQ: lint-gate-executor-shall-live-in-web-module]
- [ ] 4.5 Move smoke test executor from `lib/set_orch/merger.py` to `modules/web/set_project_web/gates.py` [REQ: smoke-gate-executor-shall-live-in-web-module]
- [ ] 4.6 Remove `_execute_e2e_gate`, `_execute_lint_gate`, `_auto_detect_e2e_command`, and all Playwright/package.json helpers from verifier.py [REQ: core-verifier-shall-not-contain-domain-specific-executors]

## 5. WebProjectType.register_gates()

- [ ] 5.1 Implement `register_gates()` in `modules/web/set_project_web/project_type.py` returning GateDefinitions for e2e, lint, smoke with position hints and per-change_type defaults [REQ: profiles-shall-register-domain-specific-gates, scenario: web-registers-e2e-lint-smoke]
- [ ] 5.2 Import gate executors from `gates.py` in register_gates [REQ: profiles-shall-register-domain-specific-gates]

## 6. Pipeline registration refactor

- [ ] 6.1 In `handle_change_done`, replace hardcoded gate registration with: collect UNIVERSAL_GATES + profile.register_gates(), resolve order, register dynamically [REQ: pipeline-shall-register-gates-from-registry]
- [ ] 6.2 In merger.py, collect post-merge gates from profile (phase="post-merge") instead of hardcoded smoke functions [REQ: smoke-gate-executor-shall-live-in-web-module]
- [ ] 6.3 Pass `GateContext` to each executor instead of individual lambda params [REQ: gates-shall-be-declared-via-gatedefinition]

## 7. Tests

- [ ] 7.1 Unit test: GateDefinition creation and fields [REQ: gates-shall-be-declared-via-gatedefinition]
- [ ] 7.2 Unit test: dynamic GateConfig — should_run/is_blocking with arbitrary gate names [REQ: gateconfig-shall-support-arbitrary-gate-names]
- [ ] 7.3 Unit test: resolve_gate_config merges universal + web profile gates for feature change [REQ: resolve-gateconfig-shall-merge-universal-and-profile, scenario: web-feature-gets-all-gates]
- [ ] 7.4 Unit test: resolve_gate_config for NullProfile — only universal gates [REQ: resolve-gateconfig-shall-merge-universal-and-profile]
- [ ] 7.5 Unit test: _resolve_gate_order — position hints produce correct ordering [REQ: pipeline-shall-register-gates-from-registry, scenario: gates-execute-in-position-order]
- [ ] 7.6 Unit test: web gate executors work from modules/web path [REQ: e2e-gate-executor-shall-live-in-web-module, scenario: e2e-gate-works-from-web-module]
- [ ] 7.7 Integration test: full pipeline with web profile — same gates, same order as before [REQ: pipeline-shall-register-gates-from-registry]
- [ ] 7.8 Run existing tests: must all pass (backwards compat) [REQ: gateconfig-shall-support-arbitrary-gate-names]
