## 1. ProjectType arch hooks (Layer 1 ABC + Core defaults)

- [x] 1.1 Add `detect_test_framework(project_dir: Path) -> Optional[str]` to `ProjectType` ABC in `lib/set_orch/profile_types.py` with a `return None` default. Add docstring documenting the contract (returns short name "vitest"|"jest"|"mocha" or None) [REQ: projecttype-exposes-test-framework-detection-hook]
- [x] 1.2 Add `detect_schema_provider(project_dir: Path) -> Optional[str]` to `ProjectType` ABC with `return None` default and docstring [REQ: projecttype-exposes-schema-provider-detection-hook]
- [x] 1.3 Add `get_design_globals_path(project_dir: Path) -> Optional[Path]` to `ProjectType` ABC with `return None` default and docstring [REQ: projecttype-exposes-design-globals-path-hook]
- [x] 1.4 Confirm `CoreProfile` in `lib/set_orch/profile_loader.py` inherits the None defaults for all three hooks (no overrides). Add a one-line comment in CoreProfile pointing to the hooks for discoverability [REQ: projecttype-exposes-test-framework-detection-hook]

## 2. WebProjectType concrete overrides (Layer 2)

- [x] 2.1 Override `detect_test_framework` in `modules/web/set_project_web/project_type.py` with glob-based detection: `vitest.config.*` → "vitest"; else `jest.config.*` → "jest"; else `.mocharc.*` → "mocha"; else None [REQ: projecttype-exposes-test-framework-detection-hook]
- [x] 2.2 Override `detect_schema_provider` checking `project_dir / "prisma" / "schema.prisma"` exists → "prisma" else None [REQ: projecttype-exposes-schema-provider-detection-hook]
- [x] 2.3 Override `get_design_globals_path` returning `project_dir / "v0-export" / "app" / "globals.css"` if file exists, else None [REQ: projecttype-exposes-design-globals-path-hook]

## 3. planner.py — replace hardcodes with hook calls

- [x] 3.1 In `lib/set_orch/planner.py` around lines 241-242 and 268, replace `vitest.config.*` glob and `["vitest","jest","mocha"]` membership test with `profile.detect_test_framework(project_dir)`. Use the returned short name (or None) in the existing logic [REQ: planner-py-uses-profile-hooks-instead-of-hardcoded-detection]
- [x] 3.2 Around lines 338 and 422, replace direct `prisma/` path checks with `profile.detect_schema_provider(project_dir)`. Branch on the returned string (currently only "prisma" is recognized; None preserves current "no schema" behavior) [REQ: planner-py-uses-profile-hooks-instead-of-hardcoded-detection]
- [x] 3.3 Around line 2802, replace `Path("v0-export") / "app" / "globals.css"` with `profile.get_design_globals_path(project_dir)`. Keep the existing fallback when the path is None (don't inject a design-tokens reference) [REQ: planner-py-uses-profile-hooks-instead-of-hardcoded-detection]
- [x] 3.4 Verify with `grep -nE "vitest|prisma|v0-export|mocha\\.config|jest\\.config" lib/set_orch/planner.py` that production code paths contain zero matches. Comments documenting the layer rule MAY remain [REQ: planner-py-uses-profile-hooks-instead-of-hardcoded-detection]

## 4. Fail-loud profile-load + universal prefix backstop

- [x] 4.1 In `lib/set_orch/templates.py::_get_test_bundling_directives`, replace the bare `except Exception: pass` with `except Exception: logger.warning("Profile load failed in templates._get_test_bundling_directives; falling back to neutral defaults", exc_info=True); profile = None` and adjust caller branches [REQ: profile-load-failure-in-test-bundling-helpers-is-logged-at-warning]
- [x] 4.2 In `lib/set_orch/planner.py::_assert_no_standalone_test_changes`, replace silent profile-load fallback with `logger.warning(..., exc_info=True)` then proceed with universal-prefix-only enforcement [REQ: profile-load-failure-in-test-bundling-helpers-is-logged-at-warning]
- [x] 4.3 In `_assert_no_standalone_test_changes`, define `_UNIVERSAL_TEST_PREFIXES = ("test-", "e2e-", "playwright-", "vitest-")` near the top of the function. Compute `prefixes = sorted(set(profile_prefixes) | set(_UNIVERSAL_TEST_PREFIXES))`. Continue using the existing regex-build path with this expanded set. Singleton-exception logic (skip exact match of `infra_name`) remains unchanged [REQ: post-merge-guard-enforces-a-universal-test-prefix-backstop]
- [x] 4.4 Update the guard's RuntimeError message to also mention "test-bundling backstop" so operators know the universal prefix matched (separate from a profile-specific prefix) [REQ: post-merge-guard-enforces-a-universal-test-prefix-backstop]

## 5. Domain decompose prompt — explicit change_type instruction

- [x] 5.1 In `lib/set_orch/templates.py::render_domain_decompose_prompt`, add a new bullet to the existing `## Constraints` block stating: "Each emitted change MUST set `change_type` to one of: `infrastructure`, `schema`, `foundational`, `feature`, `cleanup-before`, `cleanup-after`. The dispatcher's per-change model routing reads this field; if you omit it, the dispatcher falls back to the default model and the per-change routing is lost." [REQ: domain-decompose-prompt-requires-explicit-change-type-assignment]
- [x] 5.2 Verify the rendered prompt body contains all six values, the `change_type` token, and a phrase explaining the routing dependency [REQ: domain-decompose-prompt-requires-explicit-change-type-assignment]

## 6. chat.py — always pass --model

- [x] 6.1 In `lib/set_orch/chat.py::ChatSession._run_claude` (lines 102-109), restructure cmd construction so `["--model", self.model]` is always appended (right after the base `["claude", "-p", "--output-format", "stream-json", "--verbose"]`), regardless of whether `--resume` will follow. The `--permission-mode auto` flag stays only on the fresh-session branch [REQ: chatsession-claude-invocation-always-passes-model]
- [x] 6.2 Add a docstring/comment explaining the contract: every claude invocation in this codebase passes --model explicitly; resume does not exempt [REQ: chatsession-claude-invocation-always-passes-model]

## 7. Tests

- [x] 7.1 Create `tests/unit/test_profile_arch_hooks.py` with cases: CoreProfile returns None for all 3 hooks; WebProjectType detects vitest config; WebProjectType detects jest config; WebProjectType returns None when no test config; WebProjectType detects prisma schema; WebProjectType returns None when no schema; WebProjectType returns globals path when present; WebProjectType returns None when missing. Use tmp_path fixtures [REQ: projecttype-exposes-test-framework-detection-hook, REQ: projecttype-exposes-schema-provider-detection-hook, REQ: projecttype-exposes-design-globals-path-hook]
- [x] 7.2 Create `tests/unit/test_planner_layer1_purity.py` with a single regression test that scans `lib/set_orch/planner.py` and asserts zero matches for the regex `vitest|prisma|v0-export|mocha\.config|jest\.config` outside `#`-prefixed comment lines [REQ: planner-py-uses-profile-hooks-instead-of-hardcoded-detection]
- [x] 7.3 Extend `tests/unit/test_decompose_test_bundling.py` with a test that patches `load_profile` to raise, calls `_get_test_bundling_directives`, and asserts a WARNING-level log record with `exc_info` is captured (use `caplog`) [REQ: profile-load-failure-in-test-bundling-helpers-is-logged-at-warning]
- [x] 7.4 Add a test that patches `load_profile` to raise inside `_assert_no_standalone_test_changes`, feeds a plan with `playwright-smoke`, asserts a WARNING is logged AND `RuntimeError` is raised (the universal backstop catches `playwright-` even with profile load failed) [REQ: profile-load-failure-in-test-bundling-helpers-is-logged-at-warning, REQ: post-merge-guard-enforces-a-universal-test-prefix-backstop]
- [x] 7.5 Add a test using a CoreProfile-like stub returning empty `standalone_test_change_prefixes()`, feed a plan with `test-validation-suite`, assert `RuntimeError` raised naming the change (universal backstop catches `test-`) [REQ: post-merge-guard-enforces-a-universal-test-prefix-backstop]
- [x] 7.6 Add a test asserting singleton-exception still works when only profile-supplied prefixes exist AND when only universal backstop applies (singleton name `test-infrastructure-setup` passes in both modes) [REQ: post-merge-guard-enforces-a-universal-test-prefix-backstop]
- [x] 7.7 Add a test calling `render_domain_decompose_prompt` and asserting the output contains all six change_type values, the literal `change_type`, and the routing-dependency phrase [REQ: domain-decompose-prompt-requires-explicit-change-type-assignment]
- [x] 7.8 Add a test for `ChatSession._run_claude` cmd construction: fresh session → cmd contains `--model <model>` and `--permission-mode auto`, no `--resume`. Resumed session → cmd contains `--model <model>` and `--resume <id>`, no `--permission-mode`. Mutating `self.model` between calls is honored [REQ: chatsession-claude-invocation-always-passes-model]

## 8. Docs

- [x] 8.1 Add a one-line entry to release notes / docs/changelog.md (or `docs/release/` if present): "Layer-1 cleanup: planner test/schema/design detection routed through ProjectType hooks; test-bundling guards fail-loud and have a universal-prefix backstop; chat.py always passes --model on resume." [REQ: planner-py-uses-profile-hooks-instead-of-hardcoded-detection]

## Acceptance Criteria (from spec scenarios)

### Capability: profile-arch-hooks
- [x] AC-1: WHEN `CoreProfile().detect_test_framework(Path("/some/dir"))` is called for any directory layout THEN the result is `None` [REQ: projecttype-exposes-test-framework-detection-hook, scenario: core-profile-returns-none-for-test-framework]
- [x] AC-2: WHEN the project directory contains `vitest.config.ts` and `WebProjectType().detect_test_framework(project_dir)` is called THEN the result is `"vitest"` [REQ: projecttype-exposes-test-framework-detection-hook, scenario: web-profile-detects-vitest]
- [x] AC-3: WHEN the project directory contains `jest.config.js` (and no vitest config) and `WebProjectType().detect_test_framework(project_dir)` is called THEN the result is `"jest"` [REQ: projecttype-exposes-test-framework-detection-hook, scenario: web-profile-detects-jest]
- [x] AC-4: WHEN the project directory has neither vitest, jest, nor mocha config files THEN `WebProjectType().detect_test_framework(project_dir)` returns `None` [REQ: projecttype-exposes-test-framework-detection-hook, scenario: web-profile-returns-none-when-no-config-found]
- [x] AC-5: WHEN `CoreProfile().detect_schema_provider(any_dir)` is called THEN the result is `None` [REQ: projecttype-exposes-schema-provider-detection-hook, scenario: core-profile-returns-none-for-schema-provider]
- [x] AC-6: WHEN `prisma/schema.prisma` exists in `project_dir` and `WebProjectType().detect_schema_provider(project_dir)` is called THEN the result is `"prisma"` [REQ: projecttype-exposes-schema-provider-detection-hook, scenario: web-profile-detects-prisma]
- [x] AC-7: WHEN `prisma/schema.prisma` does not exist THEN `WebProjectType().detect_schema_provider(project_dir)` returns `None` [REQ: projecttype-exposes-schema-provider-detection-hook, scenario: web-profile-returns-none-when-no-schema-file]
- [x] AC-8: WHEN `CoreProfile().get_design_globals_path(any_dir)` is called THEN the result is `None` [REQ: projecttype-exposes-design-globals-path-hook, scenario: core-profile-returns-none-for-design-globals]
- [x] AC-9: WHEN `project_dir/v0-export/app/globals.css` exists THEN `WebProjectType().get_design_globals_path(project_dir)` returns the absolute Path to that file [REQ: projecttype-exposes-design-globals-path-hook, scenario: web-profile-returns-v0-export-globals-path-when-present]
- [x] AC-10: WHEN `project_dir/v0-export/app/globals.css` does not exist THEN `WebProjectType().get_design_globals_path(project_dir)` returns `None` [REQ: projecttype-exposes-design-globals-path-hook, scenario: web-profile-returns-none-when-v0-export-globals-missing]
- [x] AC-11: WHEN the codebase is scanned with `grep -nE "vitest|prisma|v0-export|mocha\\.config|jest\\.config" lib/set_orch/planner.py` THEN zero matches occur in production code paths [REQ: planner-py-uses-profile-hooks-instead-of-hardcoded-detection, scenario: grep-for-web-tokens-in-planner-py-returns-no-matches-in-detection-paths]
- [x] AC-12: WHEN the planner runs against a web project with vitest configured THEN the planner consults `profile.detect_test_framework(project_dir)` and receives `"vitest"` [REQ: planner-py-uses-profile-hooks-instead-of-hardcoded-detection, scenario: planner-test-framework-detection-uses-profile-hook]
- [x] AC-13: WHEN the planner runs against a web project with `prisma/schema.prisma` present THEN the planner consults `profile.detect_schema_provider(project_dir)` and receives `"prisma"` [REQ: planner-py-uses-profile-hooks-instead-of-hardcoded-detection, scenario: planner-schema-detection-uses-profile-hook]
- [x] AC-14: WHEN the planner needs the design tokens CSS file path THEN the planner calls `profile.get_design_globals_path(project_dir)` rather than constructing `Path("v0-export") / "app" / "globals.css"` directly [REQ: planner-py-uses-profile-hooks-instead-of-hardcoded-detection, scenario: planner-design-globals-lookup-uses-profile-hook]

### Capability: decompose-failsafe
- [x] AC-15: WHEN `_get_test_bundling_directives` is called with a `project_path` that causes `load_profile` to raise THEN a WARNING-level log record is emitted with `exc_info=True` AND the function returns the documented neutral-default directives [REQ: profile-load-failure-in-test-bundling-helpers-is-logged-at-warning, scenario: profile-load-exception-in-templates-is-logged]
- [x] AC-16: WHEN `_assert_no_standalone_test_changes` is called and `load_profile` raises THEN a WARNING-level log record is emitted with `exc_info=True` AND the guard proceeds with the universal-prefix backstop [REQ: profile-load-failure-in-test-bundling-helpers-is-logged-at-warning, scenario: profile-load-exception-in-post-merge-guard-is-logged]
- [x] AC-17: WHEN the profile returns an empty `standalone_test_change_prefixes()` list AND the merged plan contains a change named `playwright-smoke` THEN `_assert_no_standalone_test_changes` raises `RuntimeError` whose message names `playwright-smoke` and `decompose-test-bundling` [REQ: post-merge-guard-enforces-a-universal-test-prefix-backstop, scenario: standalone-playwright-change-rejected-with-empty-profile-prefixes]
- [x] AC-18: WHEN the profile is CoreProfile (no profile-supplied prefixes) AND the merged plan contains a change named `test-validation-suite` THEN `_assert_no_standalone_test_changes` raises `RuntimeError` naming `test-validation-suite` [REQ: post-merge-guard-enforces-a-universal-test-prefix-backstop, scenario: standalone-test-change-rejected-on-core-profile]
- [x] AC-19: WHEN the merged plan contains only a single change named `test-infrastructure-setup` (the default singleton name) THEN `_assert_no_standalone_test_changes` does not raise [REQ: post-merge-guard-enforces-a-universal-test-prefix-backstop, scenario: singleton-exception-still-passes]
- [x] AC-20: WHEN the profile supplies `["playwright-", "vitest-"]` AND the merged plan contains a change named `e2e-coverage-suite` THEN `_assert_no_standalone_test_changes` raises `RuntimeError` naming `e2e-coverage-suite` [REQ: post-merge-guard-enforces-a-universal-test-prefix-backstop, scenario: union-of-profile-prefixes-and-universal-backstop-applied]

### Capability: decompose-change-type-instruction
- [x] AC-21: WHEN `render_domain_decompose_prompt(...)` is invoked with any input THEN the rendered prompt body contains each of the six values: `infrastructure`, `schema`, `foundational`, `feature`, `cleanup-before`, `cleanup-after` [REQ: domain-decompose-prompt-requires-explicit-change-type-assignment, scenario: rendered-prompt-names-every-change-type-value]
- [x] AC-22: WHEN `render_domain_decompose_prompt(...)` is invoked THEN the rendered prompt body contains the substring `change_type` AND a phrase indicating it is mandatory [REQ: domain-decompose-prompt-requires-explicit-change-type-assignment, scenario: rendered-prompt-asserts-change-type-is-required]
- [x] AC-23: WHEN `render_domain_decompose_prompt(...)` is invoked THEN the rendered prompt body explains that downstream model routing uses the field [REQ: domain-decompose-prompt-requires-explicit-change-type-assignment, scenario: rendered-prompt-explains-why-change-type-matters]

### Capability: chat-explicit-model
- [x] AC-24: WHEN a `ChatSession(model="opus-4-6")` runs `_run_claude(text)` without a prior session_id THEN the constructed cmd contains `["--model", "opus-4-6"]` AND `--permission-mode auto` AND does NOT contain `--resume` [REQ: chatsession-claude-invocation-always-passes-model, scenario: fresh-session-passes-model]
- [x] AC-25: WHEN a `ChatSession(model="opus-4-6")` with `session_id="<id>"` runs `_run_claude(text)` THEN the constructed cmd contains `["--model", "opus-4-6"]` AND `--resume <id>` AND does NOT contain `--permission-mode` [REQ: chatsession-claude-invocation-always-passes-model, scenario: resumed-session-also-passes-model]
- [x] AC-26: WHEN a `ChatSession` is created with `model="sonnet"`, `session_id` set, and `self.model` is later mutated to `"opus-4-6"` before `_run_claude` runs again THEN the resulting cmd contains `--model opus-4-6` (the current `self.model`) [REQ: chatsession-claude-invocation-always-passes-model, scenario: model-change-between-resumes-is-honored]
