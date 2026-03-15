## 1. Core Module — gate_profiles.py

- [x] 1.1 Create `lib/wt_orch/gate_profiles.py` with GateConfig dataclass (fields: build, test, test_files_required, e2e, scope_check, review, spec_verify, rules, smoke, max_retries, review_model)
- [x] 1.2 Add helper methods: `should_run(gate_name)`, `is_blocking(gate_name)`, `is_warn_only(gate_name)`
- [x] 1.3 Define `BUILTIN_GATE_PROFILES` dict with all 6 change_type profiles (infrastructure, schema, foundational, feature, cleanup-before, cleanup-after)
- [x] 1.4 Define `DEFAULT_GATE_PROFILE` as feature-equivalent (all "run")
- [x] 1.5 Implement `resolve_gate_config(change, profile=None, directives=None)` with 4-layer resolution chain: built-in → profile plugin → skip flags + gate_hints → directive overrides

## 2. State — gate_hints field

- [x] 2.1 Add `gate_hints: Optional[dict] = None` field to Change dataclass in `state.py`
- [x] 2.2 Update `from_dict()` to hydrate gate_hints from JSON
- [x] 2.3 Update `to_dict()` to include gate_hints when not None (omit when None)

## 3. Profile Extension Point

- [x] 3.1 Add `gate_overrides(self, change_type: str) -> dict` method to NullProfile in `profile_loader.py`
- [x] 3.2 Add `gate_overrides(self, change_type: str) -> dict` method to ProjectType ABC in `wt-project-base/wt_project_base/base.py` with default empty-dict implementation
- [x] 3.3 Implement web-specific gate overrides in `wt-project-web/wt_project_web/project_type.py` (foundational→e2e:run+smoke:warn, schema→test_files_required:False, cleanup-after→smoke:warn)

## 4. Verifier Integration

- [x] 4.1 Import and call `resolve_gate_config()` at the start of `handle_change_done()` in `verifier.py`
- [x] 4.2 Compute `effective_max_retries` from GateConfig.max_retries (fallback to global)
- [x] 4.3 Guard VG-BUILD with `gc.should_run("build")` — skip logs "SKIPPED (gate_profile)", warn-mode failure logs warning without retry
- [x] 4.4 Guard VG-TEST with `gc.should_run("test")` — skip/warn handling, warn-fail sets test_result to "warn-fail"
- [x] 4.5 Guard VG-E2E with `gc.should_run("e2e")` — skip handling
- [x] 4.6 Guard scope check with `gc.should_run("scope_check")`
- [x] 4.7 Replace hardcoded change_type check at test-files gate with `gc.test_files_required`
- [x] 4.8 Guard VG-REVIEW with `gc.should_run("review")` — use `gc.review_model` if set
- [x] 4.9 Guard VG-RULES with `gc.should_run("rules")`
- [x] 4.10 Guard VG-SPEC-VERIFY with `gc.should_run("spec_verify")` — use `gc.is_blocking("spec_verify")` for soft-pass logic

## 5. Merger Integration

- [x] 5.1 In `post_merge_smoke()` in `merger.py`, resolve GateConfig and check `gc.should_run("smoke")` — return "skipped" if smoke is "skip"

## 6. Config — Directive Overrides

- [x] 6.1 Add `gate_overrides` directive support to `config.py` — parse nested dict from orchestration.yaml
- [x] 6.2 Pass parsed gate_overrides into `resolve_gate_config()` from engine.py where directives are available

## 7. Planning Rules — LLM Awareness

- [x] 7.1 Add gate profile section to `_PLANNING_RULES_CORE` in `templates.py` describing which gates each change_type activates
- [x] 7.2 Add optional `gate_hints` field to `_SPEC_OUTPUT_JSON`, `_SPEC_OUTPUT_JSON_DIGEST`, and `_BRIEF_OUTPUT_JSON` schema templates

## 8. Event Logging

- [x] 8.1 Add `gate_profile`, `gates_skipped`, `gates_warn_only` fields to VERIFY_GATE event emission in verifier.py

## 9. Tests

- [x] 9.1 Create `tests/test_gate_profiles.py` with unit tests: builtin profile per type, resolution chain priority, skip_test/skip_review mapping, gate_hints override, directive override, unknown type fallback, should_run/is_blocking helpers
- [x] 9.2 Add gate_hints round-trip test to existing state tests (to_dict/from_dict)

## 10. Documentation

- [x] 10.1 Update `docs/howitworks/en/07-quality-gates.md` with gate profile system description, matrix table, and resolution chain
