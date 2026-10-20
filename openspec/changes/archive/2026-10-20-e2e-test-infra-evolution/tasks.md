## Tasks

### Layer 1: Core (`lib/set_orch/`)

- [x] **T1: Add `get_test_infra_summary()` to ProjectType ABC** — `lib/set_orch/profile_types.py`: Add abstract method `get_test_infra_summary(self, project_path: Path) -> dict` returning `{"helper_files": [], "fixture_dirs": [], "patterns_detected": []}`. Add default implementation in `CoreProfile` and `NullProfile` returning empty dict.

- [x] **T2: Add `check_test_infra_usage()` to ProjectType ABC** — `lib/set_orch/profile_types.py`: Add optional method `check_test_infra_usage(self, changed_files: list, project_path: Path) -> list[str]` returning warning strings. Default implementation in `CoreProfile` returns empty list.

- [x] **T3: Dispatch injects test infra context into input.md** — `lib/set_orch/dispatcher.py`: In `_build_dispatch_context()` (around line 2060, near other context sections), call `profile.get_test_infra_summary(project_path)`. If result has any non-empty lists, append `## E2E Test Infrastructure` section to `lines` listing helper files, fixture dirs, and detected patterns.

- [x] **T4: Scope check calls test infra usage advisory** — `lib/set_orch/gate_runner.py`: In the scope_check gate execution path, call `profile.check_test_infra_usage(changed_files, project_path)` if the method exists. Log returned warnings at WARNING level with `[TEST-INFRA]` prefix. Do NOT let warnings affect gate pass/fail result.

### Layer 2: Web module (`modules/web/`)

- [x] **T5: Implement `WebProjectType.get_test_infra_summary()`** — `modules/web/set_project_web/project_type.py`: Scan `tests/e2e/helpers/**/*.ts` for helper files, `tests/e2e/fixtures/` for fixture dirs, grep `tests/e2e/*.spec.ts` for patterns (`routeWebSocket`, `page.request.post.*__test`, `page.route`). Also detect `app/__test/` or `app/(test)/` test route pages. Return structured dict.

- [x] **T6: Implement `WebProjectType.check_test_infra_usage()`** — `modules/web/set_project_web/project_type.py`: For new/modified `.spec.ts` files in `changed_files`, detect inline helper function definitions (async function at module scope that aren't `test()` callbacks). If `tests/e2e/helpers/` exists and has helpers, warn that inline helpers should be moved to shared helpers. Return list of warning strings.

- [x] **T7: Add E2E test layering planning rule** — Create `modules/web/set_project_web/templates/nextjs/rules/e2e-test-layering.md`: Instruct agents to write tests at three levels: (1) unit/integration for backend logic (vitest, no browser), (2) structural E2E (testids, visibility), (3) 1-2 functional E2E tests per change (full user flow with mock backend). Include backend/frontend separation guidance: test server-side logic independently, use Playwright only for the connection.

- [x] **T8: Update web template deployment** — Ensure `e2e-test-layering.md` rule deploys via `set-project init --project-type web`. Check `get_templates()` or template copy logic in `project_type.py` — the rule file in `templates/nextjs/rules/` should auto-deploy like other rules.

### Templates (deploy to all project types)

- [x] **T9: Create core E2E infra evolution planning rule** — Create `templates/core/rules/e2e-infra-evolution.md`: Generic rule instructing agents to (1) read `tests/e2e/helpers/` or equivalent before writing E2E tests, (2) identify what test infrastructure their feature needs, (3) extend shared helpers/fixtures, (4) write tests that use shared helpers. Keep it project-type agnostic.

- [x] **T10: Create helpers README scaffold** — Create `templates/core/rules/` or a web-specific template location for `tests/e2e/helpers/README.md` scaffold. This file documents the shared helper convention and gets deployed to consumer projects on `set-project init`. Include example helper types (mock server, seed data, auth, navigation).

### Tests

- [x] **T11: Unit test for `get_test_infra_summary()`** — `modules/web/tests/test_e2e_infra_discovery.py`: Test that `WebProjectType.get_test_infra_summary()` correctly scans helper files, fixture dirs, and detects patterns in spec files. Use a temp directory with mock project structure.

- [x] **T12: Unit test for `check_test_infra_usage()`** — `modules/web/tests/test_e2e_infra_discovery.py`: Test that inline helper detection works — a spec file with `async function waitForX(page)` triggers a warning when helpers dir exists. No warning when helpers dir doesn't exist or function is inside a test block.

- [x] **T13: Unit test for dispatch injection** — `lib/set_orch/tests/` or inline: Test that `_build_dispatch_context()` includes `## E2E Test Infrastructure` section when profile returns non-empty summary, and omits it when empty.
