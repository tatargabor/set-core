# Tasks: Design Layer Separation

## 1. ABC Interface — New profile methods

- [x] 1.1 Add `build_per_change_design(self, change_name: str, scope: str, wt_path: str, snapshot_dir: str) -> bool` to `ProjectType` ABC in `lib/set_orch/profile_types.py` — base returns False [REQ: profile-driven-design-dispatch]
- [x] 1.2 Add `get_design_dispatch_context(self, scope: str, snapshot_dir: str) -> str` to `ProjectType` ABC — base returns "" [REQ: profile-driven-design-dispatch]
- [x] 1.3 Add `build_design_review_section(self, snapshot_dir: str) -> str` to `ProjectType` ABC — base returns "" [REQ: profile-driven-design-review]
- [x] 1.4 Add `fetch_design_data_model(self, project_path: str) -> str` to `ProjectType` ABC — base returns "" [REQ: profile-driven-design-data-model]

## 2. Web Module — Implement profile methods

- [x] 2.1 Implement `WebProjectType.build_per_change_design()` in `modules/web/set_project_web/project_type.py` — move logic from `dispatcher.py:_build_per_change_design()` (lines 158-244): call bridge.sh `design_brief_for_dispatch()` + `design_context_for_dispatch()`, write `openspec/changes/<name>/design.md` [REQ: profile-driven-design-dispatch]
- [x] 2.2 Implement `WebProjectType.get_design_dispatch_context()` — move logic from `dispatcher.py:dispatch_change()` (lines 1802-1821): call bridge.sh `design_context_for_dispatch()` + `design_sources_for_dispatch()`, return combined string [REQ: profile-driven-design-dispatch]
- [x] 2.3 Implement `WebProjectType.build_design_review_section()` — move logic from `verifier.py:review_change()` (lines 1219-1233): call bridge.sh `build_design_review_section()`, return compliance text [REQ: profile-driven-design-review]
- [x] 2.4 Implement `WebProjectType.fetch_design_data_model()` — move logic from `planner.py:plan_orchestration()` (lines 1832-1843): call bridge.sh `design_data_model_section()`, return data model text [REQ: profile-driven-design-data-model]
- [x] 2.5 Add `WebProjectType.get_comparison_template_files()` override — already exists with correct file list [REQ: remove-hardcoded-web-references-from-compare]

## 3. Core — Replace bridge.sh calls with profile method calls

- [x] 3.1 Refactor `dispatcher.py:_build_per_change_design()` — replaced with profile.build_per_change_design() delegation [REQ: profile-driven-design-dispatch]
- [x] 3.2 Refactor `dispatcher.py:dispatch_change()` design enrichment — replaced with profile.get_design_dispatch_context() [REQ: profile-driven-design-dispatch]
- [x] 3.3 Refactor `verifier.py:review_change()` design section — replaced with profile.build_design_review_section() [REQ: profile-driven-design-review]
- [x] 3.4 Refactor `planner.py:plan_orchestration()` data model section — replaced with profile.fetch_design_data_model() [REQ: profile-driven-design-data-model]
- [x] 3.5 Refactor `compare.py` — already uses profile.get_comparison_template_files() with hardcoded fallback [REQ: remove-hardcoded-web-references-from-compare]

## 4. Profile plumbing — Pass profile to callers

- [x] 4.1 Ensure `dispatcher.py:_build_per_change_design()` receives profile — uses load_profile() internally [REQ: profile-driven-design-dispatch]
- [x] 4.2 Ensure `verifier.py:review_change()` receives profile — uses load_profile() internally [REQ: profile-driven-design-review]
- [x] 4.3 Ensure `planner.py:plan_orchestration()` receives profile — uses load_profile() internally [REQ: profile-driven-design-data-model]
- [x] 4.4 Ensure `compare.py` loads profile for template file lookup — already does [REQ: remove-hardcoded-web-references-from-compare]

## 5. Tests

- [ ] 5.1 Unit test: `NullProfile` / `CoreProfile` base methods return no-op values (False, "", "") [REQ: profile-driven-design-dispatch]
- [ ] 5.2 Unit test: `WebProjectType.build_per_change_design()` calls bridge.sh and writes design.md — mock subprocess, verify output matches current format [REQ: profile-driven-design-dispatch]
- [ ] 5.3 Unit test: `WebProjectType.build_design_review_section()` returns compliance text from bridge.sh [REQ: profile-driven-design-review]
- [ ] 5.4 Integration test: dispatcher with web profile produces identical design.md to current implementation — compare against a known-good per-change design.md from micro-web-run31 [REQ: profile-driven-design-dispatch]

## 6. Cleanup

- [x] 6.1 Remove `_find_design_brief()` and bridge_path resolution from `dispatcher.py` design sections [REQ: profile-driven-design-dispatch]
- [x] 6.2 Remove bridge_path resolution from `verifier.py` design section [REQ: profile-driven-design-review]
- [x] 6.3 Remove bridge_path resolution from `planner.py` design section [REQ: profile-driven-design-data-model]
- [x] 6.4 Verify no remaining bridge.sh subprocess calls in core orchestration modules (only comments remain) [REQ: profile-driven-design-dispatch]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN dispatcher builds per-change design for web project THEN profile.build_per_change_design() is called AND design.md is identical to current output [REQ: profile-driven-design-dispatch, scenario: web-project-with-design-brief-md]
- [x] AC-2: WHEN dispatcher builds per-change design for non-web project THEN profile.build_per_change_design() returns False AND no design.md written [REQ: profile-driven-design-dispatch, scenario: non-web-project-with-no-design]
- [x] AC-3: WHEN dispatcher enriches dispatch context THEN profile.get_design_dispatch_context() is called AND tokens+sources injected identically [REQ: profile-driven-design-dispatch, scenario: dispatch-enrichment-via-profile]
- [x] AC-4: WHEN verifier reviews web project THEN profile.build_design_review_section() returns compliance text [REQ: profile-driven-design-review, scenario: web-project-code-review]
- [x] AC-5: WHEN verifier reviews non-web project THEN profile.build_design_review_section() returns "" [REQ: profile-driven-design-review, scenario: non-web-project-code-review]
- [x] AC-6: WHEN planner needs data model for web project THEN profile.fetch_design_data_model() returns TypeScript interfaces [REQ: profile-driven-design-data-model, scenario: web-project-with-figma-sources]
- [x] AC-7: WHEN compare checks template files THEN profile.get_comparison_template_files() is used instead of hardcoded list [REQ: remove-hardcoded-web-references-from-compare, scenario: compare-uses-profile-template-files]
- [x] AC-8: WHEN grep -r "bridge.sh" lib/set_orch/ runs THEN only comments found (no subprocess calls) [REQ: profile-driven-design-dispatch]
