## IN SCOPE
- Pre-gate detection of `package.json` drift from `node_modules/` install marker in the verify e2e gate (web project-type only).
- Automatic package-manager install when drift is detected, before Playwright boots.
- Self-heal auto-install + one in-gate rerun when an e2e run crashes with `Cannot find module` / `MODULE_NOT_FOUND` for a package declared in `package.json`.
- Forensic log events and GateResult markers so self-healed runs are distinguishable from real passes.

## OUT OF SCOPE
- Prevention mechanisms on the agent side (agent guidance / planning rules to run `pnpm install` after modifying `package.json`).
- Dep-install logic for other gates (unit tests, lint, build) or other project types (python, rust, etc.).
- Replacement of `_reinstall_deps_if_needed` (dispatcher sync) or `_post_merge_deps_install` (merger) — those continue to operate in their existing phases.
- More than one in-gate rerun. If install + one rerun still fails, the gate returns fail and the normal `verify_retry_count` flow takes over.
- Handling of `MODULE_NOT_FOUND` for modules that are NOT declared in `package.json` — those remain real failures (bubble up).
- Transitive-dep parsing of `pnpm-lock.yaml` / `package-lock.json` to validate declared sub-deps.

## ADDED Requirements

### Requirement: Pre-gate detects dependency drift before Playwright launches
The web e2e gate (`execute_e2e_gate`) SHALL, before invoking Playwright, check whether the worktree's `package.json` has been modified more recently than the package-manager install marker (`node_modules/.modules.yaml` for pnpm, `node_modules/.package-lock.json` for npm). If drift is detected, the gate SHALL run `profile.detect_dep_install_command(wt_path)` in the worktree and log the outcome. If the install marker is absent (fresh worktree), drift SHALL be treated as detected. If `node_modules/` itself is absent, drift SHALL be treated as detected. Install timeout SHALL be 120 seconds; on timeout the gate SHALL proceed to Playwright anyway and rely on self-heal. The check SHALL NOT block the gate if the profile does not implement `detect_package_manager()` — it SHALL no-op.

#### Scenario: package.json newer than pnpm install marker
- **GIVEN** a worktree where `package.json` mtime is later than `node_modules/.modules.yaml` mtime
- **WHEN** `execute_e2e_gate` runs
- **THEN** the gate SHALL run `pnpm install` before starting Playwright
- **AND** an INFO log SHALL be emitted with event name `e2e_deps_drift_detected` and fields `wt_path`, `package_manager`, `reason="mtime"`
- **AND** an INFO log `e2e_dep_install_completed` SHALL be emitted with `duration_ms` and `exit_code`

#### Scenario: package.json and node_modules in sync
- **GIVEN** a worktree where `node_modules/.modules.yaml` mtime is at or after `package.json` mtime
- **WHEN** `execute_e2e_gate` runs
- **THEN** no install command SHALL be run
- **AND** no drift-related log event SHALL be emitted
- **AND** the gate SHALL proceed directly to Playwright

#### Scenario: node_modules directory missing
- **GIVEN** a worktree with `package.json` but no `node_modules/` directory
- **WHEN** `execute_e2e_gate` runs
- **THEN** the gate SHALL treat this as drift and run the install command
- **AND** the INFO log `e2e_deps_drift_detected` SHALL include `reason="node_modules_missing"`

#### Scenario: Install marker missing but node_modules exists
- **GIVEN** a worktree with `node_modules/` but no `.modules.yaml` or `.package-lock.json`
- **WHEN** `execute_e2e_gate` runs
- **THEN** the gate SHALL treat this as drift and run the install command
- **AND** the INFO log SHALL include `reason="marker_missing"`

#### Scenario: Pre-gate install times out
- **GIVEN** drift is detected and the install command is started
- **WHEN** the install subprocess exceeds 120 seconds without completing
- **THEN** the install SHALL be terminated
- **AND** a WARNING log SHALL be emitted with event `e2e_dep_install_timeout`
- **AND** the gate SHALL proceed to Playwright anyway (self-heal remains as a safety net)

#### Scenario: Profile without package-manager detection
- **GIVEN** a profile whose `detect_package_manager(wt_path)` returns None or is absent
- **WHEN** `execute_e2e_gate` runs
- **THEN** the drift pre-check SHALL no-op (no logs, no install)
- **AND** the gate SHALL proceed to Playwright unchanged

### Requirement: Gate self-heals on MODULE_NOT_FOUND for a declared package
When Playwright exits non-zero and the captured output contains both the literal string `MODULE_NOT_FOUND` and a regex match for `Cannot find module '([^']+)'`, and the extracted package name's first path segment (e.g. `"dotenv/config"` → `"dotenv"`) is declared as a key in the worktree's `package.json` under `dependencies` or `devDependencies`, the gate SHALL run the profile's install command once and rerun the e2e command once in-gate. The rerun SHALL NOT increment `verify_retry_count` and SHALL NOT restart the agent session. If the rerun passes, the gate SHALL return pass with a `[self-heal: installed <pkg>]` marker prepended to `GateResult.output`. If the rerun fails or also crashes without a parseable failure list, the gate SHALL return fail via the normal fail path. Self-heal SHALL run AT MOST ONCE per gate invocation.

#### Scenario: Declared-but-not-installed package causes self-heal
- **GIVEN** a worktree where `package.json` declares `"dotenv": "^16.0.0"` under `devDependencies`
- **AND** `node_modules/dotenv/` does not exist
- **AND** the e2e run exits non-zero with output containing `Cannot find module 'dotenv/config'` and `MODULE_NOT_FOUND`
- **WHEN** the gate reaches the unparseable-fail branch
- **THEN** the gate SHALL run `pnpm install` in the worktree
- **AND** the gate SHALL rerun the e2e command once with the same env and scope
- **AND** an INFO log `e2e_self_heal_installed_and_rerun` SHALL be emitted with `missing_pkg="dotenv"`, `install_duration_ms`, `rerun_outcome`
- **AND** `verify_retry_count` SHALL NOT be incremented by the self-heal

#### Scenario: Self-heal rerun passes
- **GIVEN** self-heal has run `pnpm install` and rerun the e2e command
- **WHEN** the rerun exits 0 with no flaky tests
- **THEN** the gate SHALL return GateResult pass
- **AND** `GateResult.output` SHALL be prefixed with `[self-heal: installed dotenv]\n\n`
- **AND** the baseline comparison path SHALL be skipped (the original crash was not a real test failure)

#### Scenario: Self-heal rerun still crashes without parseable failure list
- **GIVEN** self-heal ran install + rerun
- **WHEN** the rerun also exits non-zero with no parseable failure list
- **THEN** the gate SHALL return fail via the normal unparseable-fail branch
- **AND** `GateResult.retry_context` SHALL include `self-heal attempted for '<pkg>' — rerun also crashed, not a dep-drift issue` so the next agent iteration does not try the same fix

#### Scenario: MODULE_NOT_FOUND for a package NOT declared in package.json
- **GIVEN** e2e output contains `Cannot find module './nonexistent-file'` with `MODULE_NOT_FOUND`
- **AND** `./nonexistent-file` is not a declared key in `package.json`
- **WHEN** the gate reaches the unparseable-fail branch
- **THEN** self-heal SHALL NOT run
- **AND** the gate SHALL return fail via the normal unparseable-fail branch (this is a real application bug)

#### Scenario: MODULE_NOT_FOUND with scoped package name
- **GIVEN** e2e output contains `Cannot find module '@radix-ui/react-slot'` with `MODULE_NOT_FOUND`
- **AND** `package.json` declares `"@radix-ui/react-slot": "^1.2.4"` under `dependencies`
- **WHEN** the gate reaches the unparseable-fail branch
- **THEN** the first path segment `@radix-ui` alone SHALL NOT be used — the full scoped name `@radix-ui/react-slot` SHALL be used for the package.json lookup
- **AND** self-heal SHALL run because the scoped name matches a declared dep

#### Scenario: Pre-gate installed deps and Playwright still reports MODULE_NOT_FOUND
- **GIVEN** pre-gate drift was detected and install ran
- **AND** Playwright still exits with `MODULE_NOT_FOUND` for a declared package
- **WHEN** the gate reaches the unparseable-fail branch
- **THEN** self-heal SHALL run at most once — the pre-gate install does not count as the self-heal attempt
- **AND** if the second install + rerun also fails, the gate SHALL return fail (no third install attempt)

#### Scenario: Self-heal installed a package but the rerun reports real test failures
- **GIVEN** self-heal ran install + rerun
- **WHEN** the rerun exits non-zero with a parseable failure list (real failed tests)
- **THEN** the gate SHALL proceed through the normal baseline-comparison + failure-diffing path with the rerun's output
- **AND** the `[self-heal: installed <pkg>]` marker SHALL still be prepended to any GateResult.output produced

### Requirement: Forensics distinguishes self-healed runs
The gate SHALL emit structured log events that `set-run-logs` and forensics tooling can surface to distinguish self-healed passes from natural passes and from real failures. The `GateResult.output` for any self-healed pass SHALL start with a `[self-heal: installed <pkg>]` marker so dashboards and the `set-run-logs` CLI can flag the run without parsing logs.

#### Scenario: set-run-logs surfaces self-heal events
- **GIVEN** a completed run where foundation-setup e2e self-healed once
- **WHEN** a developer runs `set-run-logs <run-id> --change foundation-setup`
- **THEN** the output SHALL include at least one `e2e_self_heal_installed_and_rerun` event with its fields (missing_pkg, install_duration_ms, rerun_outcome)
- **AND** the gate's `GateResult.output` header SHALL visibly contain `[self-heal: installed <pkg>]`

#### Scenario: Forensics distinguishes pre-check install from self-heal
- **GIVEN** a gate that ran the pre-check install (drift detected) but did NOT need self-heal
- **WHEN** forensics inspects the log stream
- **THEN** only `e2e_deps_drift_detected` + `e2e_dep_install_completed` SHALL be present
- **AND** no `e2e_self_heal_installed_and_rerun` event SHALL be present
- **AND** the GateResult.output SHALL NOT contain the `[self-heal: …]` marker
