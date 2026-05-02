# Capability: e2e-testdir-drift-guard

This capability covers failure-parser classification of Playwright "No tests found" as a distinct testdir-mismatch failure class, gate-runner self-heal that rewrites `playwright.config.ts` `testDir` and `globalSetup` paths to align with the project's actual spec layout, a verify-gate canary that surfaces drift at PR time, and structured forensic logging of self-heal events.

Out of scope: modifying the merge mechanism to auto-resolve `playwright.config.ts` field-level drift (separate change), moving spec files automatically (self-heal aligns config to specs, never the reverse), parsing `playwright.config.ts` as TypeScript (line-level regex on canonical fields suffices), modifying the canonical scaffold template (already correct), the dep-drift class (covered by `e2e-dep-drift-guard`), the env-drift class (covered by `e2e-env-drift-guard`), and any Layer-1 (`lib/set_orch/`) changes (testdir conventions are web-specific).

## ADDED Requirements

### Requirement: Failure parser classifies "No tests found" as testdir-mismatch

When the e2e gate (`execute_e2e_gate` in `modules/web/set_project_web/gates.py`) sees a non-zero Playwright exit with no parseable failure list, it SHALL inspect the captured output for the literal string `Error: No tests found.`. If present, the gate SHALL classify the failure as `testdir_mismatch` and surface an actionable retry-context message identifying the divergence between `playwright.config.ts` `testDir` and the spec file paths actually present in the project.

The classification SHALL replace the legacy generic message `[no parseable failure list — likely crash, OOM, or formatter issue]` for this specific signature. The classification SHALL apply regardless of whether the gate-runner self-heal subsequently fires or recovers — it is the failure-class label and operator-facing diagnostic, separate from the recovery action.

#### Scenario: Unparseable failure with "No tests found" gets precise classification

- **GIVEN** the e2e gate runs `pnpm test:e2e tests/e2e/foo.spec.ts`
- **AND** `playwright.config.ts` declares `testDir: "e2e"`
- **AND** the spec file exists at `tests/e2e/foo.spec.ts`
- **AND** Playwright exits with code 1 and stderr contains `Error: No tests found.`
- **WHEN** the gate evaluates the failure path
- **THEN** the gate's retry-context output SHALL include a message identifying:
  - The current `testDir` value (`e2e`)
  - The directory containing the requested spec file (`tests/e2e`)
  - A hint that the two SHOULD agree
- **AND** the message SHALL NOT be the generic `[no parseable failure list — likely crash, OOM, or formatter issue]` string

#### Scenario: Other unparseable failures retain generic classification

- **GIVEN** the e2e gate sees a non-zero exit with no parseable failures
- **AND** the captured output does NOT contain `Error: No tests found.`
- **WHEN** the gate evaluates the failure path
- **THEN** the gate SHALL fall through to the existing classification flow (dep-drift / env-drift checks first; generic `[no parseable failure list ...]` if none apply)

### Requirement: Gate-runner self-heals on testdir/spec-layout drift

When the e2e gate captures a non-zero exit with no parseable failure list AND no prior self-heal has run in this gate invocation, the gate SHALL apply a testdir-drift self-heal probe ordered AFTER `_self_heal_missing_module` and `_self_heal_db_env_drift`, gated by the same single-attempt `self_heal_attempted` flag.

The probe SHALL match the captured e2e output against the literal string `Error: No tests found.`. If matched, the probe SHALL:

1. Walk the project root for `*.spec.ts` files (capping at, e.g., 200 files for safety).
2. If at least one spec file exists outside the directory currently declared as `testDir:` in `playwright.config.ts`, compute a canonical testdir candidate (the directory containing the most spec files, with a tiebreaker preferring `tests/e2e/` over `e2e/` and other paths).
3. Rewrite `playwright.config.ts` atomically (`tmpfile + os.replace`), replacing the lines matching `^\s*testDir\s*:\s*"[^"]*"` and `^\s*globalSetup\s*:\s*"[^"]*"` with the canonical paths. Preserve all other lines, leading whitespace, trailing comma, and trailing comment if present.
4. If `<canonical_testdir>/global-setup.ts` does NOT exist on disk and a stale `e2e/global-setup.ts` (or other prior path) does, copy the stale file's contents to the canonical path. Do NOT delete the stale source in this self-heal pass.
5. Invoke the e2e command once more in-gate (same args, same timeout, same env).
6. NOT increment `verify_retry_count`.
7. NOT restart the agent session.

If the rerun passes (exit 0, no flaky, no runtime errors), the gate SHALL return `pass` with `[self-heal: synced playwright.config.ts testDir from <old> to <new>]\n` prepended to `GateResult.output`. If the rerun fails or also crashes without a parseable failure list, the gate SHALL return `fail` via the normal fail path with the rerun's output.

The probe SHALL run AT MOST ONCE per gate invocation. If `_self_heal_missing_module` or `_self_heal_db_env_drift` already attempted recovery in this invocation, this probe SHALL be skipped.

The probe SHALL return `None` (no recovery attempted, gate proceeds to normal fail path) under any of:

- The captured output does not contain `Error: No tests found.`
- No `*.spec.ts` files exist anywhere in the project root.
- All discovered spec files already live under the current `testDir`.
- The regex line-replace cannot match the canonical `testDir:` or `globalSetup:` field forms (unusual config layout).
- The atomic rewrite fails (IO error, permission denied).

#### Scenario: Stale main config + correct spec layout triggers self-heal and recovers

- **GIVEN** `playwright.config.ts` declares `testDir: "e2e"` and `globalSetup: "./e2e/global-setup.ts"`
- **AND** `e2e/smoke.spec.ts` exists from a legacy scaffold
- **AND** `e2e/global-setup.ts` exists with valid content
- **AND** `tests/e2e/blog-list-with-filter.spec.ts` exists from a merged worktree (11 `test()` blocks)
- **AND** `tests/e2e/foundational-scaffold-and-shell.spec.ts` exists from another merged worktree
- **AND** no `tests/e2e/global-setup.ts` exists
- **WHEN** Playwright is invoked with `tests/e2e/blog-list-with-filter.spec.ts` as argument
- **AND** Playwright exits 1 with `Error: No tests found.`
- **AND** the gate captures the output and detects no parseable failure list
- **THEN** the gate SHALL detect the testdir-drift signature
- **AND** SHALL compute canonical_testdir = `tests/e2e` (more spec files there + tiebreaker)
- **AND** SHALL atomically rewrite `playwright.config.ts` so `testDir: "tests/e2e"` and `globalSetup: "./tests/e2e/global-setup.ts"`
- **AND** SHALL copy `e2e/global-setup.ts` content to `tests/e2e/global-setup.ts` (since the destination did not exist)
- **AND** SHALL NOT delete `e2e/smoke.spec.ts` or `e2e/global-setup.ts`
- **AND** SHALL invoke the e2e command once more
- **AND** if the rerun passes, SHALL return `GateResult("e2e", "pass", ...)` with `[self-heal: synced playwright.config.ts testDir from e2e to tests/e2e]` as the first line of `GateResult.output`
- **AND** SHALL emit INFO log `e2e_testdir_self_heal_resynced_and_rerun` with `change_name`, `resync_duration_ms`, `rerun_outcome`
- **AND** `verify_retry_count` SHALL remain unchanged

#### Scenario: No spec files anywhere → no self-heal

- **GIVEN** the e2e gate captures `Error: No tests found.` output
- **AND** the project root contains zero `*.spec.ts` files (project genuinely has no specs)
- **WHEN** the gate evaluates the testdir-drift self-heal probe
- **THEN** the probe SHALL return `None`
- **AND** the gate SHALL proceed to the normal fail path with the precise testdir-mismatch classification message

#### Scenario: Specs already under current testDir → no self-heal

- **GIVEN** `playwright.config.ts` declares `testDir: "tests/e2e"`
- **AND** all `*.spec.ts` files in the project are under `tests/e2e/`
- **AND** Playwright exits 1 with `Error: No tests found.` (operator-error: typo'd CLI argument)
- **WHEN** the gate evaluates the testdir-drift self-heal probe
- **THEN** the probe SHALL detect that all specs already live under the declared testDir
- **AND** SHALL return `None`
- **AND** the gate SHALL fail with the testdir-mismatch classification but no rewrite action

#### Scenario: Atomic rewrite fails → no self-heal, original error preserved

- **GIVEN** the testdir-drift signature matches and a canonical testdir is resolved
- **AND** `playwright.config.ts` is read-only or the regex does not match the canonical field form
- **WHEN** `_resync_playwright_config_testdir` is invoked
- **THEN** the function SHALL return `False`
- **AND** the self-heal probe SHALL return `None`
- **AND** the gate SHALL fall through to the normal fail path with the original output AND the testdir-mismatch classification message
- **AND** the gate SHALL log a WARNING with the file path and reason

#### Scenario: Self-heal does not fire when an earlier self-heal class already attempted

- **GIVEN** the e2e crash output contains BOTH `Cannot find module 'X'` (MODULE_NOT_FOUND) AND `Error: No tests found.`
- **WHEN** `_self_heal_missing_module` matches and runs install + rerun
- **THEN** the testdir-drift self-heal probe SHALL be skipped this invocation regardless of rerun outcome
- **AND** at most one `[self-heal: ...]` marker SHALL appear in `GateResult.output`

#### Scenario: Self-heal succeeds at most once per gate invocation

- **GIVEN** the testdir-drift self-heal probe runs and the rerun ALSO crashes with `Error: No tests found.`
- **WHEN** the probe evaluates the rerun's output
- **THEN** the probe SHALL NOT recurse — it SHALL return the rerun's failure verdict
- **AND** SHALL NOT attempt a second config rewrite within the same gate invocation

#### Scenario: Marker contains old and new testdir values

- **GIVEN** the testdir-drift self-heal recovers from `e2e` to `tests/e2e`
- **WHEN** the gate returns `pass`
- **THEN** `GateResult.output` SHALL begin with the literal string `[self-heal: synced playwright.config.ts testDir from e2e to tests/e2e]\n`
- **AND** the marker SHALL be machine-parseable by a regex like `\[self-heal: synced playwright\.config\.ts testDir from (\S+) to (\S+)\]`

### Requirement: Verify-gate canary warns on testdir / spec-layout divergence

The verify gate (`run_verify_gate` in `modules/web/set_project_web/verifier.py`) SHALL include a `_lint_playwright_testdir_consistency` check that runs alongside `_lint_e2e_navigation`. The check SHALL:

- Read `playwright.config.ts` if it exists at the project root (skip with `pass` if absent — non-web project or non-Playwright project).
- Extract `testDir:` value via the same regex used by the gate self-heal.
- Walk the project root for `*.spec.ts` files (capped at 200).
- Emit a `warn`-level GateResult if either:
  - The declared `testDir` directory contains zero spec files but at least one spec file exists elsewhere in the project, OR
  - Another sibling directory contains at least 3x as many spec files as the declared `testDir`.

The check SHALL emit `pass` if `playwright.config.ts` is absent, if no spec files exist anywhere, or if the declared `testDir` is the spec-densest directory (or within the 3x heuristic). The check SHALL NEVER emit `fail` — only `pass` or `warn`.

When emitting `warn`, the GateResult message SHALL identify the declared `testDir`, the canonical candidate testdir (the spec-densest directory), and the spec count in each. The message SHALL be actionable: the agent SHOULD know which value to align toward.

#### Scenario: Drift detected at PR time → warn (not fail)

- **GIVEN** `playwright.config.ts` declares `testDir: "e2e"`
- **AND** `e2e/` contains 1 spec file (`smoke.spec.ts`)
- **AND** `tests/e2e/` contains 11 spec files
- **WHEN** the verify gate runs `_lint_playwright_testdir_consistency`
- **THEN** the check SHALL emit a `warn`-level GateResult
- **AND** the message SHALL identify `testDir=e2e (1 spec)` and `tests/e2e (11 specs)` as the divergence
- **AND** the verify gate as a whole SHALL NOT fail solely because of this warn (other checks may still fail or pass independently)

#### Scenario: testDir is empty but specs exist elsewhere → warn

- **GIVEN** `playwright.config.ts` declares `testDir: "e2e"`
- **AND** `e2e/` contains zero `*.spec.ts` files
- **AND** `tests/e2e/` contains at least one `*.spec.ts` file
- **WHEN** the canary runs
- **THEN** the check SHALL emit a `warn`-level GateResult
- **AND** the message SHALL hint that `testDir` should be `tests/e2e` based on observed spec layout

#### Scenario: testDir matches spec-densest directory → pass

- **GIVEN** `playwright.config.ts` declares `testDir: "tests/e2e"`
- **AND** `tests/e2e/` contains the most spec files of any directory
- **WHEN** the canary runs
- **THEN** the check SHALL emit a `pass`-level GateResult

#### Scenario: Project has no playwright.config.ts → pass

- **GIVEN** the project has no `playwright.config.ts` (e.g. non-web project)
- **WHEN** the canary runs
- **THEN** the check SHALL emit a `pass`-level GateResult without scanning for spec files

#### Scenario: Project has no spec files anywhere → pass

- **GIVEN** `playwright.config.ts` exists with `testDir: "tests/e2e"`
- **AND** the project contains zero `*.spec.ts` files (greenfield project)
- **WHEN** the canary runs
- **THEN** the check SHALL emit a `pass`-level GateResult (no drift to flag)

#### Scenario: Heuristic threshold prevents false-positive on legitimate spread

- **GIVEN** `playwright.config.ts` declares `testDir: "tests/e2e"`
- **AND** `tests/e2e/` contains 5 spec files
- **AND** `tests/e2e/auth/` contains 2 spec files
- **AND** `tests/e2e/billing/` contains 3 spec files
- **WHEN** the canary runs (sibling dir has fewer than 3x testDir's spec count)
- **THEN** the check SHALL emit a `pass`-level GateResult (no false-positive warn)

### Requirement: Forensic logging of testdir self-heal and canary events

The gate-runner SHALL emit two structured INFO logs on testdir-drift self-heal:

- On detection: `e2e_testdir_drift_detected` with fields `change=<name>`, `wt=<wt_path>`, `stale_testdir=<old>`, `canonical_testdir=<new>`, `spec_count=<int>`.
- On post-rerun: `e2e_testdir_self_heal_resynced_and_rerun` with fields `change=<name>`, `resync_duration_ms=<int>`, `rerun_outcome=pass|fail_parseable|fail_unparseable`.

The verifier SHALL emit one structured INFO log when the canary fires `warn`:

- `playwright_testdir_consistency_warn` with fields `change=<name>`, `stale_testdir=<declared>`, `canonical_candidate=<observed>`, `stale_spec_count=<int>`, `canonical_spec_count=<int>`.

These events SHALL appear in `set/orchestration/python.log` and SHALL be surfaced by `set-run-logs` and the web dashboard's gate-output panel alongside the existing `e2e_self_heal_*` events from the dep-drift and env-drift classes.

#### Scenario: Self-heal pass is distinguishable from real pass in forensics

- **GIVEN** an e2e gate invocation where testdir-drift self-heal recovered
- **WHEN** an operator runs `set-run-logs <run-id> --gate e2e --change <name>`
- **THEN** the output SHALL include the `e2e_testdir_drift_detected` and `e2e_testdir_self_heal_resynced_and_rerun` events with their full field set
- **AND** the gate verdict line SHALL show the `[self-heal: synced playwright.config.ts testDir from <old> to <new>]` marker

#### Scenario: Verify canary warn is distinguishable in forensics

- **GIVEN** the verify canary fired `warn` on a PR
- **WHEN** an operator runs `set-run-logs <run-id> --gate verify --change <name>`
- **THEN** the output SHALL include the `playwright_testdir_consistency_warn` event with all five fields
- **AND** the verify-gate review UI SHALL render the warn at yellow severity (not red)
