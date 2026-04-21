## 1. Helpers

- [x] 1.1 Add `_install_marker_path(wt_path, package_manager)` helper in `modules/web/set_project_web/gates.py` returning the pnpm/npm marker path (`node_modules/.modules.yaml` or `node_modules/.package-lock.json`) [REQ: pre-gate-detects-dependency-drift-before-playwright-launches]
- [x] 1.2 Add `_deps_drift_reason(wt_path, package_manager)` helper returning one of `"mtime"`, `"node_modules_missing"`, `"marker_missing"`, or None (no drift) [REQ: pre-gate-detects-dependency-drift-before-playwright-launches]
- [x] 1.3 Add `_run_dep_install(wt_path, profile, timeout=120)` helper that runs `profile.detect_dep_install_command(wt_path)` via `run_command`, returns `(exit_code, duration_ms, timed_out)` [REQ: pre-gate-detects-dependency-drift-before-playwright-launches]
- [x] 1.4 Add `_extract_missing_module(e2e_output) -> str | None` helper that regex-matches `Cannot find module '([^']+)'` AND verifies `MODULE_NOT_FOUND` is present; returns the matched module name or None [REQ: gate-self-heals-on-module-not-found-for-a-declared-package]
- [x] 1.5 Add `_resolve_package_name(module_path) -> str` helper that maps `"dotenv/config"` → `"dotenv"`, `"@radix-ui/react-slot/dist/x"` → `"@radix-ui/react-slot"`, `"./relative"` → `"./relative"` (scoped-name aware) [REQ: gate-self-heals-on-module-not-found-for-a-declared-package]
- [x] 1.6 Add `_is_declared_in_package_json(wt_path, pkg_name) -> bool` helper that reads `wt_path/package.json` and checks both `dependencies` and `devDependencies` for the exact key [REQ: gate-self-heals-on-module-not-found-for-a-declared-package]

## 2. Pre-gate drift check

- [x] 2.1 Add `_ensure_deps_synced(wt_path, profile, change_name)` top-level helper in `gates.py` that composes 1.1–1.3: detects drift, runs install, emits INFO logs `e2e_deps_drift_detected` and `e2e_dep_install_completed` (or WARNING `e2e_dep_install_timeout`) with structured fields [REQ: pre-gate-detects-dependency-drift-before-playwright-launches]
- [x] 2.2 Wire `_ensure_deps_synced(wt_path, profile, change_name)` into `execute_e2e_gate` right before `_kill_stale_listeners_on_port(port)` (after pw_config / test-count / webServer checks, before env-building and port kill) [REQ: pre-gate-detects-dependency-drift-before-playwright-launches]
- [x] 2.3 Guard the pre-check with `if profile and hasattr(profile, "detect_package_manager")` — no-op when absent [REQ: pre-gate-detects-dependency-drift-before-playwright-launches]

## 3. Self-heal on MODULE_NOT_FOUND

- [x] 3.1 Add `_self_heal_missing_module(wt_path, profile, e2e_output, change_name, env, actual_e2e_cmd, e2e_timeout) -> tuple[bool, str, run_command_result | None]` helper: checks 1.4+1.5+1.6, runs install, reruns e2e once, returns `(healed, missing_pkg, rerun_result)` [REQ: gate-self-heals-on-module-not-found-for-a-declared-package]
- [x] 3.2 In `execute_e2e_gate`, inside the `if not wt_failures:` branch (currently `gates.py:760`), BEFORE the `return GateResult("e2e", "fail", …)`, call `_self_heal_missing_module`; if healed, replace `e2e_cmd_result`/`e2e_output`/`wt_failures` with the rerun's values and fall through to the normal success-or-failure-diffing path [REQ: gate-self-heals-on-module-not-found-for-a-declared-package]
- [x] 3.3 If `_self_heal_missing_module` ran but rerun still has no parseable failure list, append `"\n\nself-heal attempted for '<pkg>' — rerun also crashed, not a dep-drift issue"` to the `retry_context` before returning fail [REQ: gate-self-heals-on-module-not-found-for-a-declared-package]
- [x] 3.4 If self-heal healed and final GateResult is pass, prepend `f"[self-heal: installed {missing_pkg}]\n\n"` to `GateResult.output` before returning [REQ: gate-self-heals-on-module-not-found-for-a-declared-package]
- [x] 3.5 Emit INFO log `e2e_self_heal_installed_and_rerun` with fields `missing_pkg`, `install_duration_ms`, `rerun_outcome` (`"pass"`, `"fail_parseable"`, `"fail_unparseable"`) [REQ: gate-self-heals-on-module-not-found-for-a-declared-package]
- [x] 3.6 Cap self-heal to exactly one invocation per gate call using a local boolean flag so a rerun that also hits MODULE_NOT_FOUND does NOT trigger a second install [REQ: gate-self-heals-on-module-not-found-for-a-declared-package]

## 4. Forensics + observability

- [x] 4.1 Verify the new log events (`e2e_deps_drift_detected`, `e2e_dep_install_completed`, `e2e_dep_install_timeout`, `e2e_self_heal_installed_and_rerun`) flow through `set-run-logs` output. Update `lib/set_orch/forensics/` only if the event is filtered out by current allow-lists [REQ: forensics-distinguishes-self-healed-runs]
- [x] 4.2 Confirm that the `[self-heal: installed <pkg>]` marker survives smart-truncation of `GateResult.output` at the 32 KB boundary by placing it in the first 100 bytes [REQ: forensics-distinguishes-self-healed-runs]

## 5. Tests

- [x] 5.1 `modules/web/tests/test_gates_dep_drift.py`: unit test `_deps_drift_reason` — fresh, stale, node_modules_missing, marker_missing cases using tmp_path + os.utime [REQ: pre-gate-detects-dependency-drift-before-playwright-launches]
- [x] 5.2 Unit test `_extract_missing_module` — matches `dotenv/config` + MODULE_NOT_FOUND, rejects output missing MODULE_NOT_FOUND, rejects output without regex match [REQ: gate-self-heals-on-module-not-found-for-a-declared-package]
- [x] 5.3 Unit test `_resolve_package_name` — `dotenv/config` → `dotenv`, `@radix-ui/react-slot` → `@radix-ui/react-slot`, `@radix-ui/react-slot/dist/x` → `@radix-ui/react-slot`, `./relative-file` unchanged [REQ: gate-self-heals-on-module-not-found-for-a-declared-package]
- [x] 5.4 Unit test `_is_declared_in_package_json` — declared in dependencies, declared in devDependencies, not declared, malformed package.json (returns False, no raise) [REQ: gate-self-heals-on-module-not-found-for-a-declared-package]
- [x] 5.5 Integration test `test_execute_e2e_gate_pre_install_on_drift`: fabricate a worktree where `package.json` mtime > `node_modules/.modules.yaml`, monkey-patch `run_command` to assert install is invoked exactly once before the playwright invocation [REQ: pre-gate-detects-dependency-drift-before-playwright-launches]
- [x] 5.6 Integration test `test_execute_e2e_gate_self_heal_on_module_not_found`: first `run_command` returns exit=1 with `Cannot find module 'dotenv/config' … MODULE_NOT_FOUND`; second install exits 0; third rerun exits 0 with passing output. Assert GateResult is pass, output starts with `[self-heal: installed dotenv]`, `verify_retry_count` is not touched (that's engine-level — here just assert GateResult doesn't claim any retry signal) [REQ: gate-self-heals-on-module-not-found-for-a-declared-package]
- [x] 5.7 Integration test `test_execute_e2e_gate_no_self_heal_for_undeclared_module`: output contains `Cannot find module './app/bug'` — assert no install invoked and GateResult returns fail via unparseable path [REQ: gate-self-heals-on-module-not-found-for-a-declared-package]
- [x] 5.8 Integration test `test_execute_e2e_gate_self_heal_rerun_still_crashes`: first crash triggers self-heal, rerun also crashes unparseable — assert fail returned and `retry_context` contains `"self-heal attempted for 'dotenv' — rerun also crashed"` [REQ: gate-self-heals-on-module-not-found-for-a-declared-package]
- [x] 5.9 Integration test `test_execute_e2e_gate_self_heal_at_most_once`: first crash → install + rerun, rerun ALSO reports MODULE_NOT_FOUND — assert install is called exactly TWICE total (once pre-gate, once self-heal), NOT three times [REQ: gate-self-heals-on-module-not-found-for-a-declared-package]

## 6. Documentation

- [x] 6.1 Add a brief note to `modules/web/set_project_web/gates.py` module docstring listing the two defense layers (pre-check, self-heal) so maintainers know where to look [REQ: pre-gate-detects-dependency-drift-before-playwright-launches]
- [x] 6.2 Document the `[self-heal: installed <pkg>]` GateResult.output marker in `docs/developer-memory.md` or the web-gates section of docs so forensics users know what it means [REQ: forensics-distinguishes-self-healed-runs]

## Acceptance Criteria (from spec scenarios)

### REQ: pre-gate-detects-dependency-drift-before-playwright-launches

- [x] AC-1: WHEN `package.json` mtime > `node_modules/.modules.yaml` mtime THEN the gate runs `pnpm install` before Playwright and emits `e2e_deps_drift_detected` + `e2e_dep_install_completed` [REQ: pre-gate-detects-dependency-drift-before-playwright-launches, scenario: package-json-newer-than-pnpm-install-marker]
- [x] AC-2: WHEN `node_modules/.modules.yaml` mtime >= `package.json` mtime THEN no install is run and no drift log is emitted [REQ: pre-gate-detects-dependency-drift-before-playwright-launches, scenario: package-json-and-node-modules-in-sync]
- [x] AC-3: WHEN `node_modules/` directory is absent THEN drift is treated as detected and log includes `reason="node_modules_missing"` [REQ: pre-gate-detects-dependency-drift-before-playwright-launches, scenario: node-modules-directory-missing]
- [x] AC-4: WHEN `node_modules/` exists but install marker is absent THEN drift is treated as detected and log includes `reason="marker_missing"` [REQ: pre-gate-detects-dependency-drift-before-playwright-launches, scenario: install-marker-missing-but-node-modules-exists]
- [x] AC-5: WHEN the pre-gate install subprocess exceeds 120s THEN it is terminated, WARNING `e2e_dep_install_timeout` is logged, and the gate proceeds to Playwright anyway [REQ: pre-gate-detects-dependency-drift-before-playwright-launches, scenario: pre-gate-install-times-out]
- [x] AC-6: WHEN the profile has no `detect_package_manager` THEN the drift pre-check no-ops silently [REQ: pre-gate-detects-dependency-drift-before-playwright-launches, scenario: profile-without-package-manager-detection]

### REQ: gate-self-heals-on-module-not-found-for-a-declared-package

- [x] AC-7: WHEN a declared dep is missing and e2e crashes with `Cannot find module 'dotenv/config'` + MODULE_NOT_FOUND THEN gate runs install, reruns e2e once, emits `e2e_self_heal_installed_and_rerun`, and does NOT increment `verify_retry_count` [REQ: gate-self-heals-on-module-not-found-for-a-declared-package, scenario: declared-but-not-installed-package-causes-self-heal]
- [x] AC-8: WHEN self-heal rerun exits 0 THEN GateResult is pass, output is prefixed with `[self-heal: installed dotenv]`, and baseline comparison is skipped [REQ: gate-self-heals-on-module-not-found-for-a-declared-package, scenario: self-heal-rerun-passes]
- [x] AC-9: WHEN self-heal rerun also crashes without parseable failures THEN gate returns fail via normal unparseable-fail branch with retry_context containing `"self-heal attempted for '<pkg>' — rerun also crashed, not a dep-drift issue"` [REQ: gate-self-heals-on-module-not-found-for-a-declared-package, scenario: self-heal-rerun-still-crashes-without-parseable-failure-list]
- [x] AC-10: WHEN MODULE_NOT_FOUND references a package NOT declared in `package.json` THEN self-heal does NOT run and the gate returns fail via the normal path [REQ: gate-self-heals-on-module-not-found-for-a-declared-package, scenario: module-not-found-for-a-package-not-declared-in-package-json]
- [x] AC-11: WHEN the missing module is a scoped name (`@radix-ui/react-slot`) THEN the full scoped name (not just `@radix-ui`) is used for the package.json lookup and self-heal matches the declared dep [REQ: gate-self-heals-on-module-not-found-for-a-declared-package, scenario: module-not-found-with-scoped-package-name]
- [x] AC-12: WHEN pre-gate already installed deps and Playwright still crashes with MODULE_NOT_FOUND THEN self-heal runs at most once (pre-gate install does not count as the self-heal attempt) and a second rerun crash yields fail without a third install [REQ: gate-self-heals-on-module-not-found-for-a-declared-package, scenario: pre-gate-installed-deps-and-playwright-still-reports-module-not-found]
- [x] AC-13: WHEN self-heal rerun reports real (parseable) test failures THEN normal baseline-comparison + failure-diffing runs against the rerun's output, with `[self-heal: installed <pkg>]` marker preserved on any produced GateResult.output [REQ: gate-self-heals-on-module-not-found-for-a-declared-package, scenario: self-heal-installed-a-package-but-the-rerun-reports-real-test-failures]

### REQ: forensics-distinguishes-self-healed-runs

- [x] AC-14: WHEN `set-run-logs <run-id> --change foundation-setup` runs after a self-healed run THEN the output contains at least one `e2e_self_heal_installed_and_rerun` event with missing_pkg, install_duration_ms, rerun_outcome; and GateResult.output visibly contains the `[self-heal: installed <pkg>]` marker [REQ: forensics-distinguishes-self-healed-runs, scenario: set-run-logs-surfaces-self-heal-events]
- [x] AC-15: WHEN the pre-check ran install but self-heal did NOT THEN only `e2e_deps_drift_detected` + `e2e_dep_install_completed` events are present, no `e2e_self_heal_installed_and_rerun` event, and GateResult.output has no `[self-heal: …]` marker [REQ: forensics-distinguishes-self-healed-runs, scenario: forensics-distinguishes-pre-check-install-from-self-heal]
