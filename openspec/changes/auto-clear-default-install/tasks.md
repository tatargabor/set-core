## 1. Measure before building

- [ ] 1.1 Record one running watcher's CPU per day (`systemctl --user show -p CPUUsageNSec` over a known interval) and the count of projects init would reach (registry minus archived, `deploy: false`), in the notes below [REQ: init-installs-auto-clear-by-default]
- [ ] 1.2 Resolve the package checkout through the registry; when absent, the step prints one skip line and init still exits 0 — test with a sandbox registry that has no entry [REQ: a-missing-package-checkout-is-announced-not-fatal]

## 2. Templates with the overwrite rule (D1)

- [ ] 2.1 `lib/project/deploy.sh`: `_deploy_auto_clear` runs the package's `cli.mjs init --auto-clear` in a temp dir and lists the files it produced [REQ: init-installs-auto-clear-by-default]
- [ ] 2.2 Known-version set: blob hashes of every historical version of each produced file, from the package checkout's git history; copy only onto an absent file or a known version, otherwise keep and print "kept (locally modified)" [REQ: a-locally-modified-package-file-is-kept]
- [ ] 2.3 Skip archived, `deploy: false` and `auto_clear: false` projects with one line each [REQ: init-installs-auto-clear-by-default]
- [ ] 2.4 Tests: absent → written; older shipped version → replaced; hand-edited → byte-identical and reported; second run → nothing changes [REQ: a-locally-modified-package-file-is-kept]

## 3. Hooks (D2)

- [ ] 3.1 A separate merge step in `bin/set-deploy-hooks` adds the reload (`SessionStart`, `clear|compact`) and arm (`PostToolUse`, `Write|Edit|MultiEdit|Bash`) entries with the package's exact command strings, through `_merge_hooks_additively` [REQ: init-installs-auto-clear-by-default]
- [ ] 3.2 Own-mechanism detection: skip the reload entry when a `SessionStart` command containing `reinject` covers the clear source, the arm entry when a `PostToolUse` command contains `handoff-arm`; print the skip [REQ: a-projects-own-reload-or-arm-mechanism-is-not-duplicated]
- [ ] 3.3 Keep both entries out of the base set's "already canonical" check [REQ: a-projects-own-reload-or-arm-mechanism-is-not-duplicated]
- [ ] 3.4 Tests: empty settings → both added; a settings file already carrying the package strings → unchanged (dedup); a project reload script → package reload not added; project hooks preserved in every case [REQ: a-projects-own-reload-or-arm-mechanism-is-not-duplicated]

## 4. The watcher unit (D3, D4)

- [ ] 4.1 `templates/systemd/auto-clear.service`: watcher path, `--dir`, `--interval 60`, `--started-after <install time>`, `--auto-continue default`, PATH environment; no threshold or background flags [REQ: init-installs-auto-clear-by-default]
- [ ] 4.2 Existing-unit detection by name or by an `ExecStart` that runs this project's watcher; leave it byte-identical and name each overriding flag with the edit that removes it [REQ: an-existing-watcher-unit-is-never-rewritten]
- [ ] 4.3 Create, `daemon-reload`, `enable --now` only after the reload hook is wired (package or project); skip with a line when `systemctl --user` is unavailable [REQ: init-installs-auto-clear-by-default]
- [ ] 4.4 Tests with a fake `systemctl` on PATH and a sandbox unit dir: created + started; existing hand unit untouched and flags reported; second run does not restart [REQ: an-existing-watcher-unit-is-never-rewritten]

## 5. Dry-run (all steps)

- [ ] 5.1 `--dry-run` prints per project: templates write/keep, hooks add/skip, unit create/exists; writes nothing and calls no `systemctl` verb that changes state [REQ: dry-run-plans-and-writes-nothing]
- [ ] 5.2 Test: sha256 of the project tree and the sandbox unit dir identical before and after a dry-run [REQ: dry-run-plans-and-writes-nothing]

## 6. Doctor check (D5)

- [ ] 6.1 `lib/set_doctor/checks.py`: `auto_clear(ctx, name, path)` in `check_project`'s non-data branch; skip for archived / `deploy: false` / `auto_clear: false` [REQ: each-project-is-checked-for-auto-clear]
- [ ] 6.2 WARN cases with fixes: templates missing or not current → `set-project init --project <name>`; reload or arm wired by nobody → same; no unit → same; unit inactive → `systemctl --user start <unit>`; a threshold in the unit or a keep-going hook above 0.9 × the effective `autoCompactWindow` → names the flag and where it sits [REQ: each-project-is-checked-for-auto-clear]
- [ ] 6.3 Tests per scenario, with a sandbox HOME (settings.json carrying both window keys) and a fake `systemctl`; update the tests that enumerate check names [REQ: each-project-is-checked-for-auto-clear]

## 7. Close

- [ ] 7.1 Regression baseline set diff (`regression-baseline` skill) for `tests/unit`, plus `tests/unit/test_deploy_provenance.sh` [REQ: init-installs-auto-clear-by-default]
- [ ] 7.2 `set-project init --dry-run` against two real projects (one with a hand unit, one with nothing) — read the plan, record it [REQ: dry-run-plans-and-writes-nothing]
- [ ] 7.3 `set-doctor` on the machine: count of auto-clear WARNs per reason, recorded in the notes [REQ: each-project-is-checked-for-auto-clear]
- [ ] 7.4 `openspec validate --strict`, `/opsx:verify` with `templates/core/rules/spec-verify-gate.md` [REQ: init-installs-auto-clear-by-default]

## Acceptance Criteria (from spec scenarios)

### init-installs-auto-clear-by-default
- [ ] AC-1: WHEN init runs on a project with nothing installed THEN templates, both hooks and an active unit exist, and the unit has `--dir` and no threshold/background flags [REQ: init-installs-auto-clear-by-default, scenario: a-project-with-nothing-installed]
- [ ] AC-2: WHEN the project is archived, `deploy: false` or `auto_clear: false` THEN nothing is written and one line names the reason [REQ: init-installs-auto-clear-by-default, scenario: an-archived-data-or-opted-out-project]
- [ ] AC-3: WHEN init runs a second time THEN no file changes, no hook duplicates, no restart [REQ: init-installs-auto-clear-by-default, scenario: re-running-init-is-idempotent]

### a-locally-modified-package-file-is-kept
- [ ] AC-4: WHEN a template holds an older shipped version THEN it is replaced [REQ: a-locally-modified-package-file-is-kept, scenario: a-pristine-older-version-is-upgraded]
- [ ] AC-5: WHEN a template matches no shipped version THEN it is byte-identical and reported [REQ: a-locally-modified-package-file-is-kept, scenario: a-hand-edited-file-survives]

### a-projects-own-reload-or-arm-mechanism-is-not-duplicated
- [ ] AC-6: WHEN the project runs its own reload script for clear THEN the package reload is not added and the skip is printed [REQ: a-projects-own-reload-or-arm-mechanism-is-not-duplicated, scenario: a-project-with-its-own-reload-script]

### an-existing-watcher-unit-is-never-rewritten
- [ ] AC-7: WHEN an existing unit passes `--compact-threshold 500000` THEN it is byte-identical and the flag is named with its removal [REQ: an-existing-watcher-unit-is-never-rewritten, scenario: a-hand-written-unit-with-an-old-threshold]

### dry-run-plans-and-writes-nothing
- [ ] AC-8: WHEN dry-run runs on a project with nothing installed THEN the plan lists templates, hooks and unit, and both hashes are unchanged [REQ: dry-run-plans-and-writes-nothing, scenario: dry-run-on-a-project-with-nothing-installed]

### a-missing-package-checkout-is-announced-not-fatal
- [ ] AC-9: WHEN the package checkout cannot be resolved THEN init exits 0, says auto-clear was skipped and why, writes nothing for it [REQ: a-missing-package-checkout-is-announced-not-fatal, scenario: no-package-checkout]

### each-project-is-checked-for-auto-clear
- [ ] AC-10: WHEN templates and hooks exist but no unit THEN warn, detail "unit missing", fix `set-project init --project <name>` [REQ: each-project-is-checked-for-auto-clear, scenario: a-project-without-a-unit]
- [ ] AC-11: WHEN the unit exists but is inactive THEN warn with `systemctl --user start <unit>` [REQ: each-project-is-checked-for-auto-clear, scenario: an-inactive-unit]
- [ ] AC-12: WHEN a unit or keep-going hook passes 500000 THEN warn naming the flag and where it sits [REQ: each-project-is-checked-for-auto-clear, scenario: a-threshold-above-the-native-trigger]
- [ ] AC-13: WHEN everything is current, wired and active THEN ok [REQ: each-project-is-checked-for-auto-clear, scenario: a-complete-install]
- [ ] AC-14: WHEN the project is archived THEN skip, nothing read [REQ: each-project-is-checked-for-auto-clear, scenario: an-archived-project]

## Notes
