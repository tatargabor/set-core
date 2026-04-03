# Tasks: Init Safety and Acceptance Gate

## 1. Manifest Format and FileEntry Dataclass

- [x] 1.1 Create `FileEntry` dataclass in `profile_deploy.py` with fields: `path: str`, `protected: bool = False`, `merge: bool = False` [REQ: protected-file-annotation-in-manifest]
- [x] 1.2 Update `_resolve_file_list()` to parse both plain strings and object entries from manifest, returning `List[FileEntry]` [REQ: protected-file-annotation-in-manifest]
- [x] 1.3 Update `modules/web/set_project_web/templates/nextjs/manifest.yaml` — mark scaffold files as protected: `next.config.js`, `src/app/globals.css`, `src/lib/utils.ts`, `playwright.config.ts`, `tsconfig.json`, `vitest.config.ts`, `.env.example`. Mark `set/orchestration/config.yaml` as `merge: true` [REQ: protected-file-annotation-in-manifest]

## 2. Protected File Logic in deploy_templates

- [x] 2.1 Add `_file_matches_template(dst: Path, src: Path) -> bool` helper that compares SHA256 hashes [REQ: skip-protected-files-when-content-differs]
- [x] 2.2 Update `deploy_templates()` loop: when `force=True` and `entry.protected=True` and file exists and `not _file_matches_template()` → skip with "Skipped (protected)" message [REQ: skip-protected-files-when-content-differs]
- [x] 2.3 When `force=True` and `entry.protected=True` and file exists and `_file_matches_template()` → overwrite normally (file unchanged from template) [REQ: skip-protected-files-when-content-differs]

## 3. Additive YAML Merge for Config Files

- [x] 3.1 Add `_merge_yaml_additive(existing_path: Path, template_path: Path) -> bool` function that loads both YAMLs, adds missing keys from template, writes back [REQ: additive-yaml-merge-for-config-files]
- [x] 3.2 Update `deploy_templates()` loop: when `entry.merge=True` and file exists → call `_merge_yaml_additive()` instead of `shutil.copy2`, emit "Merged: <path>" message [REQ: additive-yaml-merge-for-config-files]
- [x] 3.3 When `entry.merge=True` and file does not exist → copy as-is (normal deploy) [REQ: additive-yaml-merge-for-config-files]

## 4. max_parallel Default Change

- [x] 4.1 Update `lib/set_orch/config.py` `DIRECTIVE_DEFAULTS["max_parallel"]` from 3 to 1 [REQ: default-max-parallel-is-1]
- [x] 4.2 Update `modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml` to set `max_parallel: 1` [REQ: default-max-parallel-is-1]

## 5. Planner Acceptance-Tests Directive (Part 1 — planner-time)

- [x] 5.1 Add acceptance-tests directive section to `render_decompose_prompt()` in `lib/set_orch/templates.py` after the "Test-per-change requirement" section [REQ: planner-includes-acceptance-tests-change]
- [x] 5.2 The directive MUST instruct the planner to: always include `acceptance-tests` change (type `test`), depends_on all others, last phase [REQ: planner-includes-acceptance-tests-change]
- [x] 5.3 The directive MUST instruct the planner to: analyze spec domains for cross-domain data flows, multi-actor interactions, and sequential workflows spanning 3+ features — list each as a named journey in the scope [REQ: planner-extracts-cross-domain-journeys-from-spec]

## 6. Agent Methodology Rules — Core (Part 2a — generic, in templates.py)

- [x] 6.1 The planner-generated scope for `acceptance-tests` MUST include generic methodology rules appended to the journey list [REQ: journey-test-methodology-rules-in-directive]
- [x] 6.2 Rule: ISOLATION — self-contained spec files, API-based preconditions in beforeAll [REQ: journey-test-methodology-rules-in-directive]
- [x] 6.3 Rule: DATA STRATEGY — read seed for reads, fresh test user for writes, discover seed by reading seed file [REQ: journey-test-methodology-rules-in-directive]
- [x] 6.4 Rule: THIRD-PARTY SERVICES — check .env for test keys, use test mode or test up-to-boundary [REQ: journey-test-methodology-rules-in-directive]
- [x] 6.5 Rule: IDEMPOTENCY — unique IDs, afterAll cleanup, tolerant assertions [REQ: journey-test-methodology-rules-in-directive]
- [x] 6.6 Rule: FIX-UNTIL-PASS — iterative fix loop, re-run only failed, document if budget exhausted [REQ: fix-until-pass-execution-loop]
- [x] 6.7 Rule: COVERAGE — verify all testable ACs covered, add tests for gaps, document non-testable ACs as exempt [REQ: acceptance-criteria-coverage-verification]

## 7. Agent Methodology Rules — Web Module (Part 2b — Playwright-specific)

- [x] 7.1 Add `acceptance_test_methodology()` method to `ProjectType` ABC in `lib/set_orch/profile_types.py` returning `str` (empty default) [REQ: journey-test-methodology-rules-in-directive]
- [x] 7.2 Implement `acceptance_test_methodology()` in `WebProjectType` (`modules/web/`) with Playwright patterns: `test.describe.serial()`, `browser.newContext()` + `newPage()` in beforeAll, `journey-*.spec.ts` naming [REQ: journey-test-methodology-rules-in-directive]
- [x] 7.3 In `render_decompose_prompt()`: call `profile.acceptance_test_methodology()` and append result to the acceptance-tests scope template [REQ: journey-test-methodology-rules-in-directive]

## 8. Update max-parallel-default Spec

- [x] 8.1 Verify the existing spec at `openspec/specs/max-parallel-default/spec.md` matches the new default value after archiving this change [REQ: default-max-parallel-is-1]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN manifest.yaml contains `{path: "next.config.js", protected: true}` THEN _resolve_file_list() returns FileEntry with protected=True [REQ: protected-file-annotation-in-manifest, scenario: manifest-with-protected-files]
- [x] AC-2: WHEN manifest.yaml contains plain string `- .gitignore` THEN _resolve_file_list() returns FileEntry(path=".gitignore", protected=False, merge=False) [REQ: protected-file-annotation-in-manifest, scenario: backward-compatible-plain-string-entries]
- [x] AC-3: WHEN re-init with --force AND protected file SHA256 differs from template THEN file NOT overwritten AND message says "Skipped (protected)" [REQ: skip-protected-files-when-content-differs, scenario: protected-file-modified-by-project]
- [x] AC-4: WHEN re-init with --force AND protected file SHA256 matches template THEN file overwritten normally [REQ: skip-protected-files-when-content-differs, scenario: protected-file-unchanged-from-template]
- [x] AC-5: WHEN re-init AND merge-enabled config has {a:1,b:2} AND template has {a:99,b:88,c:3} THEN result is {a:1,b:2,c:3} [REQ: additive-yaml-merge-for-config-files, scenario: config-file-with-new-keys-in-template]
- [x] AC-6: WHEN no max_parallel in CLI or config THEN orchestrator dispatches at most 1 change [REQ: default-max-parallel-is-1, scenario: no-explicit-max-parallel-configured]
- [x] AC-7: WHEN planner decomposes spec with 3+ features THEN output includes acceptance-tests change with depends_on all others [REQ: planner-includes-acceptance-tests-change, scenario: standard-decomposition-with-features]
- [x] AC-8: WHEN spec has domains with cross-domain data flow THEN planner lists named journeys in acceptance-tests scope [REQ: planner-extracts-cross-domain-journeys-from-spec, scenario: domains-with-data-flow-between-them]
- [x] AC-9: WHEN acceptance-tests agent finishes THEN every testable spec AC has at least one covering journey test [REQ: acceptance-criteria-coverage-verification, scenario: coverage-self-check]
- [x] AC-10: WHEN re-init on fresh project THEN all files deployed normally regardless of protection flags [REQ: template-file-deployment-respects-protection, scenario: first-init-deploys-all-files-normally]
