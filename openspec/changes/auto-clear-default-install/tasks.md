## 1. Measure before building

- [x] 1.1 Record one running watcher's CPU per day (`systemctl --user show -p CPUUsageNSec` over a known interval) and the count of projects init would reach (registry minus archived, `deploy: false`), in the notes below [REQ: init-installs-auto-clear-by-default]
- [x] 1.2 Resolve the package checkout through the registry; when absent, the step prints one skip line and init still exits 0 — test with a sandbox registry that has no entry [REQ: a-missing-package-checkout-is-announced-not-fatal]

## 2. Templates with the overwrite rule (D1)

- [x] 2.1 `lib/project/deploy.sh`: `_deploy_auto_clear` runs the package's `cli.mjs init --auto-clear` in a temp dir and lists the files it produced [REQ: init-installs-auto-clear-by-default]
- [x] 2.2 Known-version set: blob hashes of every historical version of each produced file, from the package checkout's git history; copy only onto an absent file or a known version, otherwise keep and print "kept (locally modified)" [REQ: a-locally-modified-package-file-is-kept]
- [x] 2.3 Skip archived, `deploy: false` and `auto_clear: false` projects with one line each [REQ: init-installs-auto-clear-by-default]
- [x] 2.4 Tests: absent → written; older shipped version → replaced; hand-edited → byte-identical and reported; second run → nothing changes [REQ: a-locally-modified-package-file-is-kept]

## 3. Hooks (D2)

- [x] 3.1 A separate merge step in `bin/set-deploy-hooks` adds the reload (`SessionStart`, `clear|compact`) and arm (`PostToolUse`, `Write|Edit|MultiEdit|Bash`) entries with the package's exact command strings, through `_merge_hooks_additively` [REQ: init-installs-auto-clear-by-default]
- [x] 3.2 Own-mechanism detection: skip the reload entry when a `SessionStart` command containing `reinject` covers the clear source, the arm entry when a `PostToolUse` command contains `handoff-arm`; print the skip [REQ: a-projects-own-reload-or-arm-mechanism-is-not-duplicated]
- [x] 3.3 Keep both entries out of the base set's "already canonical" check [REQ: a-projects-own-reload-or-arm-mechanism-is-not-duplicated]
- [x] 3.4 Tests: empty settings → both added; a settings file already carrying the package strings → unchanged (dedup); a project reload script → package reload not added; project hooks preserved in every case [REQ: a-projects-own-reload-or-arm-mechanism-is-not-duplicated]
- [x] 3.5 Write `<tree>/.set/handoff/.reload-wired-at` (ISO-8601 UTC, `Z`) when the reload entry is first added or its command changes; never on a no-op merge (D3 stamp contract)

## 4. The watcher unit (D3, D4)

- [x] 4.1 `templates/systemd/auto-clear.service`: watcher path, `--dir`, `--interval 60`, `--auto-continue default`, PATH environment; no threshold or background flag. Until the package's `started-after-self-exclusion` ships, the unit passes `--started-after` with the time in the tree's `.set/handoff/.reload-wired-at`; after it ships, the flag goes (D3) [REQ: init-installs-auto-clear-by-default]
- [x] 4.2 Existing-unit detection by name or by an `ExecStart` that runs this project's watcher; leave it byte-identical and name each overriding flag with the edit that removes it [REQ: an-existing-watcher-unit-is-never-rewritten]
- [x] 4.3 Create, `daemon-reload`, `enable --now` only after the reload hook is wired (package or project); skip with a line when `systemctl --user` is unavailable [REQ: init-installs-auto-clear-by-default]
- [x] 4.4 Tests with a fake `systemctl` on PATH and a sandbox unit dir: created + started; existing hand unit untouched and flags reported; second run does not restart [REQ: an-existing-watcher-unit-is-never-rewritten]

## 5. Dry-run (all steps)

- [x] 5.1 `--dry-run` prints per project: templates write/keep, hooks add/skip, unit create/exists; writes nothing and calls no `systemctl` verb that changes state [REQ: dry-run-plans-and-writes-nothing]
- [x] 5.2 Test: sha256 of the project tree and the sandbox unit dir identical before and after a dry-run [REQ: dry-run-plans-and-writes-nothing]

## 6. Doctor check (D5)

- [x] 6.1 `lib/set_doctor/checks.py`: `auto_clear(ctx, name, path)` in `check_project`'s non-data branch; skip for archived / `deploy: false` / `auto_clear: false` [REQ: each-project-is-checked-for-auto-clear]
- [x] 6.2 WARN cases with fixes: templates missing or not current → `set-project init --project <name>`; reload or arm wired by nobody → same; no unit → same; unit inactive → `systemctl --user start <unit>`; a threshold in the unit or a keep-going hook above 0.9 × the effective `autoCompactWindow` → names the flag and where it sits [REQ: each-project-is-checked-for-auto-clear]
- [x] 6.3 Tests per scenario, with a sandbox HOME (settings.json carrying both window keys) and a fake `systemctl`; update the tests that enumerate check names [REQ: each-project-is-checked-for-auto-clear]

## 7. Close

- [x] 7.1 Regression baseline set diff (`regression-baseline` skill) for `tests/unit`, plus `tests/unit/test_deploy_provenance.sh` [REQ: init-installs-auto-clear-by-default]
- [x] 7.2 `set-project init --dry-run` against two real projects (one with a hand unit, one with nothing) — read the plan, record it [REQ: dry-run-plans-and-writes-nothing]
- [x] 7.3 `set-doctor` on the machine: count of auto-clear WARNs per reason, recorded in the notes [REQ: each-project-is-checked-for-auto-clear]
- [ ] 7.4 `openspec validate --strict`, `/opsx:verify` with `templates/core/rules/spec-verify-gate.md` [REQ: init-installs-auto-clear-by-default]

## Acceptance Criteria (from spec scenarios)

### init-installs-auto-clear-by-default
- [x] AC-1: WHEN init runs on a project with nothing installed THEN templates, both hooks and an active unit exist, and the unit has `--dir` and no threshold/background flags [REQ: init-installs-auto-clear-by-default, scenario: a-project-with-nothing-installed]
- [x] AC-2: WHEN the project is archived, `deploy: false` or `auto_clear: false` THEN nothing is written and one line names the reason [REQ: init-installs-auto-clear-by-default, scenario: an-archived-data-or-opted-out-project]
- [x] AC-3: WHEN init runs a second time THEN no file changes, no hook duplicates, no restart [REQ: init-installs-auto-clear-by-default, scenario: re-running-init-is-idempotent]

### a-locally-modified-package-file-is-kept
- [x] AC-4: WHEN a template holds an older shipped version THEN it is replaced [REQ: a-locally-modified-package-file-is-kept, scenario: a-pristine-older-version-is-upgraded]
- [x] AC-5: WHEN a template matches no shipped version THEN it is byte-identical and reported [REQ: a-locally-modified-package-file-is-kept, scenario: a-hand-edited-file-survives]

### a-projects-own-reload-or-arm-mechanism-is-not-duplicated
- [x] AC-6: WHEN the project runs its own reload script for clear THEN the package reload is not added and the skip is printed [REQ: a-projects-own-reload-or-arm-mechanism-is-not-duplicated, scenario: a-project-with-its-own-reload-script]

### an-existing-watcher-unit-is-never-rewritten
- [x] AC-7: WHEN an existing unit passes `--compact-threshold 500000` THEN it is byte-identical and the flag is named with its removal [REQ: an-existing-watcher-unit-is-never-rewritten, scenario: a-hand-written-unit-with-an-old-threshold]

### dry-run-plans-and-writes-nothing
- [x] AC-8: WHEN dry-run runs on a project with nothing installed THEN the plan lists templates, hooks and unit, and both hashes are unchanged [REQ: dry-run-plans-and-writes-nothing, scenario: dry-run-on-a-project-with-nothing-installed]

### a-missing-package-checkout-is-announced-not-fatal
- [x] AC-9: WHEN the package checkout cannot be resolved THEN init exits 0, says auto-clear was skipped and why, writes nothing for it [REQ: a-missing-package-checkout-is-announced-not-fatal, scenario: no-package-checkout]

### each-project-is-checked-for-auto-clear
- [x] AC-10: WHEN templates and hooks exist but no unit THEN warn, detail "unit missing", fix `set-project init --project <name>` [REQ: each-project-is-checked-for-auto-clear, scenario: a-project-without-a-unit]
- [x] AC-11: WHEN the unit exists but is inactive THEN warn with `systemctl --user start <unit>` [REQ: each-project-is-checked-for-auto-clear, scenario: an-inactive-unit]
- [x] AC-12: WHEN a unit or keep-going hook passes 500000 THEN warn naming the flag and where it sits [REQ: each-project-is-checked-for-auto-clear, scenario: a-threshold-above-the-native-trigger]
- [x] AC-13: WHEN everything is current, wired and active THEN ok [REQ: each-project-is-checked-for-auto-clear, scenario: a-complete-install]
- [x] AC-14: WHEN the project is archived THEN skip, nothing read [REQ: each-project-is-checked-for-auto-clear, scenario: an-archived-project]

## Notes

- 2026-11-23, group 6 (doctor check): `lib/set_doctor/auto_clear.py`, wired in `check_project`'s
  deploy branch; `deploy: false` adds `auto-clear` to its skip set; archived projects never reach
  `check_project` (`archived_entries`, covered by `test_archived_entries_are_left_out_of_a_full_run`).
  `tests/unit/test_doctor_auto_clear.py` 14 tests; three mutants (unit always active, ExecStart not
  matched to the tree, native trigger ignored) each fail one test; restore checked with `cmp`.
  Until group 2 ships, the fix `set-project init --project <name>` does not yet install anything —
  the doctor and init are meant to ship as one release.
- Run against four real projects the same day: the package checkout is AHEAD of what the projects
  carry (an unpushed package commit changed `clear-gate.mjs` and `watch-auto-clear.sh`), so all
  three installed projects read "templates not current"; one project lacks the arm hook; two pin
  keep-going `--threshold 500000`; the framework repo itself has nothing installed.
- Package interface (answered on the bus 2026-11-23): hook command strings are stable; the unit
  needs no new required flag (`--idle-minutes`/`--idle-floor` default on); a package-owned
  `versions --json` manifest is planned but not built — keep the git-history walk until it is;
  keep-going may stop needing `--threshold` once it reads the gate's default — do not merge it with
  a pinned value then.
- 2026-11-23, group 3 (hooks): `set-deploy-hooks --auto-clear [--dry-run]` is its own mode — it
  merges only the two package entries through `_merge_hooks_additively` (both removal flags off)
  and exits before the base set's canonical check, so 3.3 holds by construction. A reinject wired
  for `startup` only does not count as an own reload; an empty matcher does. `--dry-run` without
  `--auto-clear` is refused rather than silently writing. `tests/unit/test_deploy_hooks_auto_clear.py`
  11 tests; three mutants (matcher test dropped, no-op exit dropped, dry-run branch dropped) fail
  1/1/2; the base-set suites (wave board, wait detect, memory absent, question relay) 149 passed.
- keep-going stays unmerged: it is opt-in in the package. The package confirmed the same day that
  it reads the gate's default and its printed hooks carry no `--threshold`; a project that wants
  it merges those strings, and the doctor reports any pinned value.
- 2026-11-23, 1.1 measured: five running watchers over the same 2591 s used 19.8–59.4 s CPU, i.e.
  0.8–2.3 % of one core each — about 11–33 CPU-minutes a day per watcher. Init would reach 43
  projects (registry minus 25 archived and 2 `deploy: false`); the full fleet would cost roughly
  0.3–1 core continuously. Not a blocker for the code, but the rollout should go project by
  project (Migration Plan step 3), and the watcher's per-minute cost is a question for the package.
- 2026-11-23, groups 2/4/5: `lib/set_orch/auto_clear_deploy.py`, called from `_deploy_auto_clear`
  in `lib/project/deploy.sh` right after `deploy_set_tools` in `set-project init` (both real and
  dry-run). The package installer runs in a temp dir; its output is located in the package by blob
  and the shipped-version set comes from `git log --follow`. The unit passes `--started-after` from
  the stamp (now, when the project carries none) per D3's safety rule.
  `tests/unit/test_auto_clear_deploy.py` 13 tests; four mutants (hash rule off, `--follow` dropped,
  existing-unit check off, dry-run guard off) fail 1/1/2/1. `tests/unit/test_deploy_provenance.sh`
  32/32.
- 2026-11-23, 7.2: `set-project init --dry-run` against a project with a hand unit (templates
  "would upgrade" because the package checkout is ahead of it; the profile kept as locally
  modified; the unit "exists, left as is") and against one with nothing (10 files, both hooks, a
  new unit planned). A sha256 snapshot of each tree plus the user unit directory was identical
  before and after both runs.
- The package checkout's HEAD is what init deploys, pushed or not. On 2026-11-23 it carried
  unpushed package commits, so no real init has been run yet — a real run would ship those.
- 2026-11-23, 7.3: `set-doctor --json --offline` on the machine — 43 auto-clear records, 41 warn,
  2 skip (`deploy: false`), 0 ok. Reasons (a record can carry several): no watcher unit 33; no arm
  hook 30; templates missing 29; no reload hook 29; templates not current 12 (every installed
  project, because the package checkout is ahead of all of them); keep-going pinned at 500000 3;
  unit inactive 1 (a hand unit that is `disabled`, with no watcher process for that tree — left
  alone: whether that project should be cleared automatically is the owner's call).
- 2026-11-23, 7.1: baseline = a worktree at HEAD with this change's two commits reverted, run
  with the three import roots and the leak assertion (0 leaks). Working tree 77 failed / 21
  errors, baseline 78 / 21; the only difference is one test failing in the baseline and passing
  here (`test_paths.py::TestResolveProjectName::test_resolve_with_explicit_path`) — no regression.
  The working tree also carried other sessions' uncommitted files at the time.
- 2026-11-23 ~21:50, package 98590a6 rolled out to the running watchers: the auto-clear step
  (`python -m set_orch.auto_clear_deploy`, dry-run first) upgraded the six package templates in
  five trees (profiles kept as locally modified, units byte-identical), then each unit was
  restarted; all five `active` with no error line a minute later. Not rolled out: one flagship
  consumer whose own reinject is wired and whose unit pins `--background-work-blocks false` (the
  step would add the arm hook — its owner's call), one unit whose project is not in the registry,
  and set-agent-comm (restarted 21:26, templates current).
