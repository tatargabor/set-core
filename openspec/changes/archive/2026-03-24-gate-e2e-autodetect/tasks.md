## 1. Profile Loader Fallback

- [x] 1.1 Add `detect_e2e_command(project_path: str) -> Optional[str]` method to NullProfile in `lib/set_orch/profile_loader.py` returning None [REQ: nullprofile-shall-provide-detect-e2e-command-interface]
- [x] 1.2 After the entry_points loop (line ~195), add direct import fallback: try `importlib.import_module(f"set_project_{type_name}")`, look for a class with `ProjectType` suffix, instantiate and cache [REQ: profile-loader-shall-fall-back-to-direct-import]
- [x] 1.3 Log at info level on successful direct import fallback, warning level on import failure [REQ: profile-loader-shall-fall-back-to-direct-import]
- [x] 1.4 Add unit test: mock entry_points returning empty, mock importlib.import_module succeeding → verify profile loaded [REQ: profile-loader-shall-fall-back-to-direct-import, scenario: entry-points-empty-but-package-importable]
- [x] 1.5 Add unit test: mock entry_points empty, mock import_module raising ImportError → verify NullProfile returned [REQ: profile-loader-shall-fall-back-to-direct-import, scenario: entry-points-empty-and-package-not-importable]

## 2. E2E Auto-Detect Logic

- [x] 2.1 Create `_auto_detect_e2e_command(wt_path: str, profile=None) -> str` function in `lib/set_orch/verifier.py` that: (a) tries profile.detect_e2e_command(wt_path) if profile has the method, (b) reads package.json for test:e2e/e2e/playwright scripts, (c) falls back to "npx playwright test" if playwright.config exists [REQ: e2e-gate-shall-auto-detect-command-when-not-configured]
- [x] 2.2 Helper `_read_package_json_scripts(wt_path: str) -> dict` — read package.json scripts section, return empty dict on failure [REQ: e2e-gate-shall-auto-detect-command-when-not-configured]
- [x] 2.3 In `_execute_e2e_gate`, at line 2162, replace early return with auto-detect: if e2e_command empty, call _auto_detect_e2e_command; if still empty, return skipped [REQ: e2e-gate-shall-auto-detect-command-when-not-configured]
- [x] 2.4 Pass profile to _execute_e2e_gate — add profile parameter, thread from handle_change_done [REQ: e2e-gate-shall-auto-detect-command-when-not-configured]
- [x] 2.5 Add unit test: playwright.config.ts exists + package.json has test:e2e → auto-detects command [REQ: e2e-gate-shall-auto-detect-command-when-not-configured, scenario: auto-detect-from-package-json]
- [x] 2.6 Add unit test: playwright.config.ts exists + no script → falls back to npx playwright test [REQ: e2e-gate-shall-auto-detect-command-when-not-configured, scenario: auto-detect-fallback-npx]
- [x] 2.7 Add unit test: no playwright config → returns skipped [REQ: e2e-gate-shall-auto-detect-command-when-not-configured, scenario: no-playwright-config-skip]

## 3. Mandatory E2E for Feature Changes

- [x] 3.1 In _execute_e2e_gate, after e2e_test_count==0 check (line 2171), differentiate: if command was auto-detected AND playwright config exists, return GateResult("fail") with retry_context "E2E tests required for feature changes" [REQ: feature-changes-shall-fail-when-playwright-exists-but-no-tests]
- [x] 3.2 Track whether e2e_command was auto-detected vs explicit — add `auto_detected: bool` local variable [REQ: feature-changes-shall-fail-when-playwright-exists-but-no-tests]
- [x] 3.3 Add unit test: auto-detected + playwright config + no test files → fail [REQ: feature-changes-shall-fail-when-playwright-exists-but-no-tests, scenario: playwright-config-exists-but-no-tests]
- [x] 3.4 Add unit test: explicit e2e_command + no test files → skipped (existing behavior preserved) [REQ: feature-changes-shall-fail-when-playwright-exists-but-no-tests, scenario: explicit-config-no-tests-skip]

## 4. Integration

- [x] 4.1 Run existing tests: `python -m pytest tests/unit/test_verifier.py tests/test_gate_profiles.py -x` — must pass [REQ: e2e-gate-shall-auto-detect-command-when-not-configured]
- [x] 4.2 Verify auto-detect does NOT activate when e2e_command is explicitly set in directives [REQ: e2e-gate-shall-auto-detect-command-when-not-configured]
