## 1. Module layer (`lib/set_doctor/modules.py`, new)

- [ ] 1.1 Resolve the `doctors.d` directory the same way as the registry (`SET_CONFIG_DIR` → `XDG_CONFIG_HOME/set-core` → `~/.config/set-core`), reusing the registry's resolver, not a second copy [REQ: module-doctors-are-discovered-from-declarations]
- [ ] 1.2 Load declarations: required `module`, `command` (list), `contract`, `install`; optional `timeout_s`. Report a `fail` naming the file for one that is unreadable or incomplete, and a `fail` naming both files for a duplicate `module` [REQ: module-doctors-are-discovered-from-declarations]
- [ ] 1.3 Run each declared module once, with a timeout and with `SET_DOCTOR_CHILD=1` in its environment. A command not on PATH is a `warn` "declared but not installed on this machine" with the `install` hint as the fix [REQ: each-declared-module-runs-once-and-its-records-reach-the-right-project]
- [ ] 1.4 Parse `doctor/1`: reject an unknown `schema` and any status outside the four as a `fail` of that module, never dropping its records silently. A timeout or an unparseable output is a `fail` carrying the error tail [REQ: module-doctors-speak-one-record-contract]
- [ ] 1.5 Merge: tag every record with `module`. Join records carrying `path` to a registered project by real path. Put unmatched ones under the module's own section [REQ: each-declared-module-runs-once-and-its-records-reach-the-right-project]
- [ ] 1.6 Log module start, exit code, duration and record count (INFO), and every rejected report (WARNING) [REQ: each-declared-module-runs-once-and-its-records-reach-the-right-project]

## 2. Adapters for the pre-contract doctors

- [ ] 2.1 Move the `sac doctor --json` call behind an adapter (`sac.doctor/1` → per-project records) that reproduces today's `bus` records. A `sac` declaration takes over its invocation (one run), and a `doctor/1` declaration bypasses the adapter [REQ: the-two-pre-contract-module-doctors-keep-working-through-adapters]
- [ ] 2.2 Same for `set-kb doctor --json` per project, reproducing today's `kb` records [REQ: the-two-pre-contract-module-doctors-keep-working-through-adapters]
- [ ] 2.3 Bus severity in the `sac` adapter, from `hooks` and `live`: a live seat with no `session-start` or no `watch-guard` is a `fail` naming the seat(s) and the missing hook(s), with `sac install` in the project as the fix. No hooks and no live seat stays a `warn` [REQ: every-registered-project-is-checked]
- [ ] 2.4 Duplicate wiring: a hook kind with more than one carrier is a `warn` naming the carriers [REQ: every-registered-project-is-checked]

## 3. set-doctor core (`lib/set_doctor/checks.py`, `cli.py`)

- [ ] 3.1 Gone registry paths: collect them into one `stale` warn (count, names, fix `set-project prune --dry-run`). No per-entry `fail`, and no further checks on them [REQ: every-registered-project-is-checked]
- [ ] 3.2 `Check` gains an optional `module`. `--json` stays `set-doctor/1` with the field added [REQ: every-check-reports-a-status-and-the-command-that-fixes-it]
- [ ] 3.3 Recursion guard: under `SET_DOCTOR_CHILD=1`, run no module doctors and emit one `skip` saying the parent runs them [REQ: a-module-doctor-that-runs-set-doctor-does-not-recurse]
- [ ] 3.4 `run_all` runs the module layer once, in parallel with the per-project checks, and the text output shows module records in each project's block with the module name [REQ: each-declared-module-runs-once-and-its-records-reach-the-right-project]
- [ ] 3.5 `install.sh` writes set-core's own `set-kb` declaration into `doctors.d`, idempotently [REQ: module-doctors-are-discovered-from-declarations]

## 4. Tests (`tests/unit/test_set_doctor.py`, new `tests/unit/test_doctor_modules.py`)

- [ ] 4.1 One test per spec scenario in both delta specs, in the existing sandbox-machine style (temp HOME, registry, `SET_CONFIG_DIR`, fake module commands as small scripts) [REQ: module-doctors-speak-one-record-contract]
- [ ] 4.2 Regression: with an empty `doctors.d` and a `sac`/`set-kb` stub, the records equal the pre-change records except for the `stale` grouping and the new bus `fail` [REQ: the-two-pre-contract-module-doctors-keep-working-through-adapters]
- [ ] 4.3 Prove each new test: revert the matching source change (`git stash push -- <paths>`, never a pathspec-less stash) and see the test fail, then restore it and assert the restore took [REQ: every-registered-project-is-checked]
- [ ] 4.4 Set-diff `tests/unit` failures against a baseline worktree (`regression-baseline` skill) [REQ: every-check-reports-a-status-and-the-command-that-fixes-it]

## 5. Docs and the real machine

- [ ] 5.1 `docs/reference/set-doctor.md`: the `doctor/1` contract, the declaration format with an example, `SET_DOCTOR_CHILD`, the `stale` record, the bus `fail` rule [REQ: module-doctors-speak-one-record-contract]
- [ ] 5.2 Run `set-doctor` on this machine and record the measured before/after summary and the live-seat bus `fail`s it now names. The B-193 entry is updated with the evidence and closed with the sha [REQ: every-registered-project-is-checked]

## 6. Coordination (other repositories — agreed, not edited from here)

- [ ] 6.1 Agent-bus module: ask its session (start one through the fleet if none is live) to write a `doctors.d/sac.json` declaration from its setup command, and later to print `doctor/1` with the D4 bus rule in its own records [REQ: module-doctors-are-discovered-from-declarations]
- [ ] 6.2 Family doctor: ask its session (fleet if none is live) to read `set-doctor --json` instead of the exit code, drop its duplicated bus regex in favour of the `sac` fields, and declare itself relying on `SET_DOCTOR_CHILD` [REQ: a-module-doctor-that-runs-set-doctor-does-not-recurse]
- [ ] 6.3 Record both answers (agreed / declined / pending) in this change before archiving [REQ: module-doctors-are-discovered-from-declarations]

## Acceptance Criteria (from spec scenarios)

### module-doctors-speak-one-record-contract
- [ ] AC-1: WHEN a declared module prints a `doctor/1` object with one `warn` record carrying a `fix` THEN the report contains that record with `module` set [REQ: module-doctors-speak-one-record-contract, scenario: a-conforming-module-report-is-merged]
- [ ] AC-2: WHEN a declared module prints `schema: doctor/9` THEN a `fail` names the unexpected schema and the module is not shown as clean [REQ: module-doctors-speak-one-record-contract, scenario: an-unknown-contract-is-a-failure-not-an-absence]

### module-doctors-are-discovered-from-declarations
- [ ] AC-3: WHEN a declaration for module `example` is added and its command prints a valid report THEN the next run includes its records [REQ: module-doctors-are-discovered-from-declarations, scenario: a-new-module-is-picked-up-without-a-code-change]
- [ ] AC-4: WHEN a `doctors.d` file is not valid JSON THEN a `fail` names the file and every other module still runs [REQ: module-doctors-are-discovered-from-declarations, scenario: a-broken-declaration-is-reported]

### each-declared-module-runs-once-and-its-records-reach-the-right-project
- [ ] AC-5: WHEN a module reports a `fail` with a registered project's path THEN that project's block shows it and the JSON record carries `module` and `project` [REQ: each-declared-module-runs-once-and-its-records-reach-the-right-project, scenario: a-per-project-record-lands-on-its-project]
- [ ] AC-6: WHEN a module's command exceeds its timeout THEN a `fail` says it timed out and the rest of the report is complete [REQ: each-declared-module-runs-once-and-its-records-reach-the-right-project, scenario: a-module-that-hangs]

### a-declared-module-that-is-not-installed-is-reported
- [ ] AC-7: WHEN a declaration's command is not on PATH THEN a `warn` carries the install hint as fix [REQ: a-declared-module-that-is-not-installed-is-reported, scenario: a-second-developers-machine-without-the-module]

### the-two-pre-contract-module-doctors-keep-working-through-adapters
- [ ] AC-8: WHEN `doctors.d` is empty THEN every project still gets its `bus` and `kb` records [REQ: the-two-pre-contract-module-doctors-keep-working-through-adapters, scenario: no-declaration-no-regression]
- [ ] AC-9: WHEN a `sac` declaration exists THEN `sac doctor` runs once, not twice [REQ: the-two-pre-contract-module-doctors-keep-working-through-adapters, scenario: a-declaration-replaces-the-built-in-run]

### a-module-doctor-that-runs-set-doctor-does-not-recurse
- [ ] AC-10: WHEN a declared module runs `set-doctor --json` THEN the inner run runs no module doctors and the outer run finishes once [REQ: a-module-doctor-that-runs-set-doctor-does-not-recurse, scenario: the-family-doctor-is-declared-and-calls-set-doctor]

### every-check-reports-a-status-and-the-command-that-fixes-it
- [ ] AC-11: WHEN one check fails THEN exit 1 and the record carries a `fix` [REQ: every-check-reports-a-status-and-the-command-that-fixes-it, scenario: a-failing-check-sets-the-exit-code]
- [ ] AC-12: WHEN only warnings THEN exit 0, and 1 with `--strict` [REQ: every-check-reports-a-status-and-the-command-that-fixes-it, scenario: warnings-alone-pass-unless-strict]
- [ ] AC-13: WHEN a record comes from the agent-bus module THEN it carries `"module": "sac"` [REQ: every-check-reports-a-status-and-the-command-that-fixes-it, scenario: a-modules-record-says-where-it-came-from]

### every-registered-project-is-checked
- [ ] AC-14: WHEN two registry paths do not exist THEN one `stale` warn names both with `set-project prune --dry-run`, and no `fail` [REQ: every-registered-project-is-checked, scenario: a-registered-path-is-gone]
- [ ] AC-15: WHEN `.set-version` is three commits behind THEN deploy warns "3 commits behind" [REQ: every-registered-project-is-checked, scenario: a-project-behind-this-checkout]
- [ ] AC-16: WHEN the MCP registration's `CLAUDE_PROJECT_DIR` is elsewhere THEN the MCP check warns naming both [REQ: every-registered-project-is-checked, scenario: an-mcp-registration-that-points-elsewhere]
- [ ] AC-17: WHEN an entry has `deploy: false` THEN deploy, MCP and bus are `skip` [REQ: every-registered-project-is-checked, scenario: a-data-repository]
- [ ] AC-18: WHEN a project has a live seat and no hooks THEN the bus record is a `fail` naming the seat and `session-start` + `watch-guard`, fix `sac install` [REQ: every-registered-project-is-checked, scenario: a-live-session-in-a-project-off-the-bus]
- [ ] AC-19: WHEN a live project has `session-start` but no `watch-guard` THEN the bus record is a `fail` naming `watch-guard` [REQ: every-registered-project-is-checked, scenario: a-live-session-without-the-watch-guard]
- [ ] AC-20: WHEN no hooks and no live seat THEN the bus record is a `warn` [REQ: every-registered-project-is-checked, scenario: off-the-bus-and-idle]
- [ ] AC-21: WHEN `session-start` comes from both settings and a plugin THEN the bus record warns naming both carriers [REQ: every-registered-project-is-checked, scenario: a-hook-wired-twice]
