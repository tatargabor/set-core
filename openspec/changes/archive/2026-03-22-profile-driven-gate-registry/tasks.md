## 1. GateDefinition dataclass

- [x] 1.1 Add `GateDefinition` dataclass to `lib/set_orch/gate_runner.py`: name, executor, position, phase, defaults, own_retry_counter, extra_retries, result_fields, run_on_integration [REQ: gates-shall-be-declared-via-gatedefinition]
- [x] 1.2 Add `register_gates() -> list[GateDefinition]` to ProjectType ABC in `lib/set_orch/profile_types.py` returning empty list [REQ: profiles-shall-register-domain-specific-gates]
- [x] 1.3 Add `_resolve_gate_order(gates: list[GateDefinition]) -> list[GateDefinition]` helper in `lib/set_orch/gate_runner.py` — topological sort by position hints (start, after:X, before:X, end) [REQ: pipeline-shall-register-gates-from-registry]

## 2. Dynamic GateConfig

- [x] 2.1 Refactor `GateConfig` in `gate_profiles.py` from fixed-field dataclass to dict-based class with `_gates: dict[str, str]` [REQ: gateconfig-shall-support-arbitrary-gate-names]
- [x] 2.2 Preserve `should_run()`, `is_blocking()`, `is_warn_only()` using dict lookup with "run" default [REQ: gateconfig-shall-support-arbitrary-gate-names]
- [x] 2.3 Keep `test_files_required`, `max_retries`, `review_model`, `review_extra_retries` as direct attributes (not in gates dict) [REQ: gateconfig-shall-support-arbitrary-gate-names]
- [x] 2.4 Define `UNIVERSAL_DEFAULTS`: per change_type defaults for universal gates only (extract from BUILTIN_GATE_PROFILES, without e2e/lint/smoke) [REQ: resolve-gateconfig-shall-merge-universal-and-profile]
- [x] 2.5 Refactor `resolve_gate_config()`: universal defaults → universal change_type defaults → profile gate defaults → gate_overrides → per-change → directives [REQ: resolve-gateconfig-shall-merge-universal-and-profile]
- [x] 2.6 Remove `BUILTIN_GATE_PROFILES` dict (replaced by UNIVERSAL_DEFAULTS + profile.register_gates defaults) [REQ: resolve-gateconfig-shall-merge-universal-and-profile]

## 3. Universal gate definitions in core

- [x] 3.1 Create `UNIVERSAL_GATES` list in `lib/set_orch/verifier.py` with GateDefinitions for: build, test, scope_check, test_files, review, rules, spec_verify — each with position hints and result_fields [REQ: gates-shall-be-declared-via-gatedefinition]
- [x] 3.2 Make `commit_results()` in GatePipeline use `result_fields` from GateDefinition instead of hardcoded `gate_field_map` — pass gate definitions to pipeline constructor or register [REQ: gates-shall-be-declared-via-gatedefinition]

## 4. Move web-specific gate executors to modules/web

- [x] 4.1 Create `modules/web/set_project_web/gates.py` with `execute_e2e_gate(ctx) -> GateResult` — move from verifier.py, preserve all logic [REQ: e2e-gate-executor-shall-live-in-web-module]
- [x] 4.2 Move `_execute_lint_gate` to `modules/web/set_project_web/gates.py` as `execute_lint_gate(ctx) -> GateResult` [REQ: lint-gate-executor-shall-live-in-web-module]
- [x] 4.3 Move `_parse_playwright_config`, `_count_e2e_tests`, `_check_e2e_runtime_errors`, `_get_or_create_e2e_baseline` helpers to `modules/web/set_project_web/gates.py` [REQ: e2e-gate-executor-shall-live-in-web-module]
- [x] 4.4 Move `_load_forbidden_patterns`, `_extract_added_lines` to `modules/web/set_project_web/gates.py` [REQ: lint-gate-executor-shall-live-in-web-module]
- [x] 4.5 Remove `_execute_e2e_gate`, `_execute_lint_gate`, `_auto_detect_e2e_command`, and all Playwright/package.json helpers from verifier.py [REQ: core-verifier-shall-not-contain-domain-specific-executors]

## 5. WebProjectType.register_gates()

- [x] 5.1 Implement `register_gates()` in `modules/web/set_project_web/project_type.py` returning GateDefinitions for e2e and lint with position hints and per-change_type defaults [REQ: profiles-shall-register-domain-specific-gates, scenario: web-registers-e2e-lint-smoke]
- [x] 5.2 Import gate executors from `gates.py` in register_gates [REQ: profiles-shall-register-domain-specific-gates]

## 6. Pipeline registration refactor

- [x] 6.1 In `handle_change_done`, replace hardcoded gate registration with: collect UNIVERSAL_GATES + profile.register_gates(phase="pre-merge"), resolve order, register dynamically [REQ: pipeline-shall-register-gates-from-registry]
- [x] 6.2 Pass executor-specific params via lambda closures (no GateContext — existing pattern preserved) [REQ: gates-shall-be-declared-via-gatedefinition]

## 7. Merger cleanup — dead code and profile hooks

- [x] 7.1 Delete dead smoke pipeline code from merger.py: `_run_smoke_pipeline`, `_blocking_smoke_pipeline`, `_nonblocking_smoke_pipeline`, `_collect_smoke_screenshots` [REQ: dead-smoke-pipeline-shall-be-removed]
- [x] 7.2 Add `post_merge_hooks(change_name, state_file)` to ProjectType ABC with no-op default [REQ: web-post-merge-hooks-shall-live-in-web-module]
- [x] 7.3 Move `merge_i18n_sidecars()` from merger.py to `modules/web/set_project_web/post_merge.py`, call it from WebProjectType.post_merge_hooks() [REQ: web-post-merge-hooks-shall-live-in-web-module]
- [x] 7.4 Simplify merger ff-success path: replace `_post_merge_deps_install()` with `profile.post_merge_install(".")` (method already exists), call `profile.post_merge_hooks()`, keep `_post_merge_custom_command` and `_run_plugin_post_merge_directives` [REQ: web-post-merge-hooks-shall-live-in-web-module]

## 8. Merge queue — integrate, verify, ff-only (serialized)

- [x] 8.1 Rewrite `execute_merge_queue`: for each change — integrate main, run integration gates, then ff-only. Serialized: each change sees fresh main from the previous merge. [REQ: merge-queue-shall-serialize-integration]
- [x] 8.2 Add `_integrate_for_merge(wt_path, change_name) -> str` helper: merge main into branch in worktree, return "ok" or "conflict". Check exit code (unlike current _try_merge). [REQ: merge-queue-shall-serialize-integration]
- [x] 8.3 Run integration gates after integration, before ff-only: collect gates with `run_on_integration=True`, execute in worktree. If any blocking gate fails → merge-blocked. [REQ: merge-queue-shall-run-integration-gates]
- [x] 8.4 Set `run_on_integration=True` on universal gates: build, test. Set on web profile gates: e2e. Leave False on: review, rules, spec_verify, scope_check, lint. [REQ: merge-queue-shall-run-integration-gates]
- [x] 8.5 Simplify `merge_change()`: remove ff-fail → status="done" re-queue path. ff-only is guaranteed after successful integration. On unexpected ff-fail, mark merge-blocked (not re-queue). [REQ: merge-queue-shall-serialize-integration]
- [x] 8.6 Delete `_try_merge()` — replaced by integrate → verify → ff in queue loop [REQ: merge-queue-shall-serialize-integration]
- [x] 8.7 Delete `_compute_conflict_fingerprint()` and `_seen_conflict_fingerprints` — conflict = merge-blocked immediately [REQ: merge-queue-shall-serialize-integration]
- [x] 8.8 Delete `_post_merge_build_check()` — replaced by integration gates (runs BEFORE ff, not after) [REQ: merge-queue-shall-run-integration-gates]
- [x] 8.9 Remove `ff_retry_count`, `merge_retry_count` fields from merge flow — no retries needed [REQ: merge-queue-shall-serialize-integration]
- [x] 8.10 Keep `retry_merge_queue()` for retrying merge-blocked changes with fresh integration + verify (after other merges may have resolved conflict source) [REQ: merge-queue-shall-serialize-integration]

## 9. Tests

- [x] 9.1 Unit test: GateDefinition creation and fields [REQ: gates-shall-be-declared-via-gatedefinition]
- [x] 9.2 Unit test: dynamic GateConfig — should_run/is_blocking/is_warn_only with arbitrary gate names [REQ: gateconfig-shall-support-arbitrary-gate-names]
- [x] 9.3 Unit test: resolve_gate_config merges universal + web profile gates for feature change [REQ: resolve-gateconfig-shall-merge-universal-and-profile, scenario: web-feature-gets-all-gates]
- [x] 9.4 Unit test: resolve_gate_config for NullProfile — only universal gates [REQ: resolve-gateconfig-shall-merge-universal-and-profile]
- [x] 9.5 Unit test: _resolve_gate_order — position hints produce correct ordering [REQ: pipeline-shall-register-gates-from-registry, scenario: gates-execute-in-position-order]
- [x] 9.6 Unit test: web gate executors work from modules/web path [REQ: e2e-gate-executor-shall-live-in-web-module, scenario: e2e-gate-works-from-web-module]
- [x] 9.7 Unit test: merge queue — sequential integration, each change gets fresh main [REQ: merge-queue-shall-serialize-integration]
- [x] 9.8 Unit test: merge queue — integration conflict → merge-blocked, queue continues [REQ: merge-queue-shall-serialize-integration]
- [x] 9.9a Unit test: integration gates — build fail after integration → merge-blocked [REQ: merge-queue-shall-run-integration-gates]
- [x] 9.9b Unit test: integration gates — build+test pass → ff-only proceeds [REQ: merge-queue-shall-run-integration-gates]
- [x] 9.9 Integration test: full pipeline with web profile — same gates, same order as before [REQ: pipeline-shall-register-gates-from-registry]
- [x] 9.10 Run existing tests: must all pass (backwards compat) [REQ: gateconfig-shall-support-arbitrary-gate-names]
