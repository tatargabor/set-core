## 1. Job file and CLI (`bin/set-wave-board`)

- [x] 1.1 Job file schema, `init`, `add` with evidence validation, `set` (fast lane), stable formatting, no absolute paths [REQ: a-job-is-a-tracked-registration-file]
- [x] 1.2 Evidence evaluation: `openspec-tasks` (with archive fallback), `path-exists`, `commit`; absence yields no verdict [REQ: status-is-derived-from-evidence]
- [x] 1.3 Precedence: evidence replaces status except a manual `blocked` / `skipped` [REQ: evidence-wins-except-a-manual-block-or-skip]
- [x] 1.4 `project` evidence through the registry (`SET_CORE_REGISTRY` override), unresolved reporting, nested `project` refused [REQ: evidence-from-another-project-is-resolved-by-registry-name]
- [x] 1.5 `sync`: rewrite only on change, `updated`/`by` only on status change, payload with content hash, `PUSH` line, `.set/waveboard/.gitignore` [REQ: sync-is-idempotent-and-writes-the-database-payload]
- [x] 1.6 `pushed`, `pending`, `--json` output [REQ: the-push-is-the-agents-act-recorded-per-machine]

## 2. Board page

- [x] 2.1 `templates/waveboard/page.html`: waves, items, chips, per-wave and overall counts, last sync; `db` subscription on `board/state`; seed fallback; never writes [REQ: the-board-page-is-read-only-and-works-offline]
- [x] 2.2 `page` and `render` (standalone by default, `--bare` for publishing) [REQ: the-board-page-is-read-only-and-works-offline]

## 3. Hook and deployment

- [x] 3.1 `bin/set-hook-waveboard`: silent exits, quiet sync, per-job backoff, block reason with the exact push procedure, subprocess timeout [REQ: a-stop-hook-makes-the-agent-push]
- [x] 3.2 `bin/set-deploy-hooks`: Stop entry gains the hook; canonical check requires it [REQ: the-hook-reaches-existing-projects]
      Verified by mutation: the old canonical check over base hooks + a project Stop hook
      delivered the waveboard hook 0 times; the new one delivers it once and keeps the project hook.
- [x] 3.3 `install.sh`: link both commands [REQ: the-hook-reaches-existing-projects]

## 4. Skill

- [x] 4.1 `.claude/skills/set/wave-board/SKILL.md`: when to use, creation flow, push procedure, fast lane vs evidence, cross-machine notes [REQ: the-push-is-the-agents-act-recorded-per-machine]

## 5. Tests

- [x] 5.1 `tests/unit/test_wave_board.py` covering every scenario below [REQ: sync-is-idempotent-and-writes-the-database-payload]
- [x] 5.2 `tests/unit` failure set diffed against a baseline run at the parent commit [REQ: sync-is-idempotent-and-writes-the-database-payload]
      Measured 2026-10-07: baseline at `02c7f3d0` in an isolated worktree (three import roots,
      leak check 0) = 99 failed / 4986 passed / 21 errors; this change = 98 failed / 5014
      passed / 21 errors. Set diff: no new failure; one baseline failure
      (`test_paths.py::TestResolveProjectName::test_resolve_with_explicit_path`) passes in the
      main checkout, which depends on the checkout's path, not on this change. +28 passed =
      the 27 new tests + that one.

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN init then add runs THEN the job file holds the wave and the item at `todo` [REQ: a-job-is-a-tracked-registration-file, scenario: creating-a-job-and-adding-an-item]
- [x] AC-2: WHEN add is given malformed evidence THEN it exits non-zero and the file is unchanged [REQ: a-job-is-a-tracked-registration-file, scenario: evidence-that-is-malformed-is-refused-when-added]
- [x] AC-3: WHEN a tasks file is partly checked THEN the item is `doing` [REQ: status-is-derived-from-evidence, scenario: partly-checked-tasks-file]
- [x] AC-4: WHEN only the archived tasks file exists THEN the item is `done` [REQ: status-is-derived-from-evidence, scenario: archived-change]
- [x] AC-5: WHEN a path-exists path is missing THEN a manual `doing` stays [REQ: status-is-derived-from-evidence, scenario: no-evidence-yet]
- [x] AC-6: WHEN a manual `done` meets unchecked boxes THEN the item is `doing` [REQ: evidence-wins-except-a-manual-block-or-skip, scenario: an-agents-premature-done-is-corrected]
- [x] AC-7: WHEN a `blocked` item's evidence says done THEN it stays `blocked` [REQ: evidence-wins-except-a-manual-block-or-skip, scenario: a-blocked-item-stays-blocked]
- [x] AC-8: WHEN the named project is registered and satisfied THEN the item is `done` [REQ: evidence-from-another-project-is-resolved-by-registry-name, scenario: a-registered-project]
- [x] AC-9: WHEN the named project is not registered THEN the status is unchanged and reported unresolved [REQ: evidence-from-another-project-is-resolved-by-registry-name, scenario: a-project-not-registered-here]
- [x] AC-10: WHEN sync runs twice with nothing changed THEN nothing is rewritten and no PUSH follows a recorded push [REQ: sync-is-idempotent-and-writes-the-database-payload, scenario: a-second-sync-changes-nothing]
- [x] AC-11: WHEN a payload changes and is then recorded pushed THEN pending lists it before and not after [REQ: the-push-is-the-agents-act-recorded-per-machine, scenario: push-cycle]
- [x] AC-12: WHEN `stop_hook_active` is true THEN the hook is silent [REQ: a-stop-hook-makes-the-agent-push, scenario: the-hooks-own-continuation-does-not-loop]
- [x] AC-13: WHEN the hook runs again inside the backoff THEN it is silent [REQ: a-stop-hook-makes-the-agent-push, scenario: backoff]
- [x] AC-16: WHEN the Stop event comes from a linked worktree THEN the hook is silent [REQ: a-stop-hook-makes-the-agent-push, scenario: a-linked-worktree-is-not-the-boards-source]
- [x] AC-14: WHEN render runs THEN the file carries the seed and opens offline as a snapshot [REQ: the-board-page-is-read-only-and-works-offline, scenario: offline-render]
- [x] AC-15: WHEN deploy runs twice over base hooks plus a project hook THEN the project hook survives and the waveboard hook appears once [REQ: the-hook-reaches-existing-projects, scenario: a-project-that-already-has-the-base-hooks-and-its-own]
