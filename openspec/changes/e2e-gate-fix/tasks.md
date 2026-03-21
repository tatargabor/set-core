# Tasks: e2e-gate-fix

## 1. Playwright config parser helper

- [x] 1.1 Add `_parse_playwright_config(wt_path)` function to `verifier.py` that finds `playwright.config.ts` or `.js`, reads it, extracts `testDir` via regex, and detects `webServer` block presence [REQ: e2e-test-discovery-reads-playwright-config]
- [x] 1.2 Return a dict with `config_path`, `test_dir` (or None), and `has_web_server` (bool) [REQ: e2e-test-discovery-reads-playwright-config]

## 2. Fix test discovery

- [x] 2.1 Refactor `_count_e2e_tests()` to call `_parse_playwright_config()` and use the parsed `test_dir` [REQ: e2e-test-discovery-reads-playwright-config]
- [x] 2.2 When `test_dir` is None (not in config), search fallback directories: `tests/e2e/`, `e2e/`, `test/e2e/`, and Playwright default `tests/` [REQ: e2e-test-discovery-reads-playwright-config]
- [x] 2.3 Return 0 when no Playwright config exists (unchanged behavior) [REQ: e2e-test-discovery-reads-playwright-config]

## 3. WebServer-aware E2E gate

- [x] 3.1 In `_execute_e2e_gate()`, call `_parse_playwright_config()` to get webServer info [REQ: e2e-gate-performs-health-check-before-running-playwright]
- [x] 3.2 When `has_web_server` is True: skip port allocation, skip health check, run `e2e_command` without `PW_PORT` env, skip pkill cleanup [REQ: e2e-gate-performs-health-check-before-running-playwright]
- [x] 3.3 When `has_web_server` is False: keep existing port allocation + health check + pkill flow [REQ: e2e-gate-performs-health-check-before-running-playwright]
- [x] 3.4 Remove the `has_pw_config` check that duplicates the config detection (now handled by `_parse_playwright_config`) [REQ: e2e-gate-performs-health-check-before-running-playwright]

## 4. Skip reason diagnostics

- [x] 4.1 Add output to GateResult when skipping due to no `e2e_command`: "e2e_command not configured" [REQ: e2e-gate-skip-reasons-are-diagnostic]
- [x] 4.2 Add output when skipping due to no Playwright config: "no playwright.config.ts/js found in worktree" [REQ: e2e-gate-skip-reasons-are-diagnostic]
- [x] 4.3 Add output when skipping due to 0 test files: include searched directories in message [REQ: e2e-gate-skip-reasons-are-diagnostic]
- [x] 4.4 Ensure the existing health check skip message is preserved for the non-webServer path [REQ: e2e-gate-skip-reasons-are-diagnostic]

## 5. Fix phase-end E2E

- [x] 5.1 In `run_phase_end_e2e()`, call `_parse_playwright_config()` for the current working directory [REQ: e2e-gate-performs-health-check-before-running-playwright]
- [x] 5.2 When `has_web_server` is True: skip PW_PORT env var, skip pkill cleanup [REQ: e2e-server-cleanup-matches-startup-mode]
- [x] 5.3 When `has_web_server` is False: keep existing port + cleanup logic [REQ: e2e-server-cleanup-matches-startup-mode]

## 6. Gate pipeline integration

- [x] 6.1 Ensure `e2e_output` is stored in `change.extras` even when result is "skipped" (for diagnostics) [REQ: vg-pipeline-gate-pipeline-handle_change_done]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN playwright.config.ts has webServer block THEN gate skips health check and runs e2e_command directly [REQ: e2e-gate-performs-health-check-before-running-playwright, scenario: playwright-config-has-webserver-block]
- [x] AC-2: WHEN playwright.config.ts has no webServer block THEN gate performs health check on allocated port [REQ: e2e-gate-performs-health-check-before-running-playwright, scenario: playwright-config-has-no-webserver-block]
- [x] AC-3: WHEN playwright.config.ts specifies testDir: "./e2e" THEN _count_e2e_tests finds tests there [REQ: e2e-test-discovery-reads-playwright-config, scenario: playwright-config-specifies-testdir]
- [x] AC-4: WHEN playwright.config.ts has no testDir THEN search fallback dirs (tests/, e2e/, tests/e2e/, test/e2e/) [REQ: e2e-test-discovery-reads-playwright-config, scenario: playwright-config-does-not-specify-testdir]
- [x] AC-5: WHEN E2E skips for any reason THEN GateResult.output contains descriptive reason [REQ: e2e-gate-skip-reasons-are-diagnostic, scenario: skip-due-to-no-test-files]
- [x] AC-6: WHEN Playwright manages server via webServer THEN no pkill commands run [REQ: e2e-server-cleanup-matches-startup-mode, scenario: playwright-manages-server-no-cleanup]
