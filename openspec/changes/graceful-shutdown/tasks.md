# Tasks: Graceful Shutdown

## 1. Sentinel Shutdown Command

- [x] 1.1 Add `--shutdown` flag parsing to `bin/wt-sentinel` argument handling [REQ: sentinel-graceful-shutdown-command]
- [x] 1.2 Implement SIGUSR1 handler in sentinel main loop that triggers shutdown sequence [REQ: sentinel-graceful-shutdown-command]
- [x] 1.3 Implement `--shutdown` flag logic: read PID file, send SIGUSR1 to running sentinel, wait for exit [REQ: sentinel-graceful-shutdown-command]
- [x] 1.4 Add shutdown timeout: wait up to 60s for agents, then SIGKILL remaining [REQ: sentinel-graceful-shutdown-command]

## 2. Agent Graceful Stop

- [x] 2.1 Add SIGTERM trap in `bin/wt-loop` that sets `stop_requested=true` flag [REQ: agent-graceful-stop-on-sigterm]
- [x] 2.2 Add post-iteration check: if `stop_requested`, commit uncommitted work with WIP message and exit [REQ: agent-graceful-stop-on-sigterm]
- [x] 2.3 Write `last_commit` hash to loop-state.json before exit [REQ: agent-graceful-stop-on-sigterm]
- [x] 2.4 Handle idle state: if SIGTERM received between iterations, exit immediately [REQ: agent-graceful-stop-on-sigterm]

## 3. State Persistence

- [x] 3.1 Add `shutdown_at` field to state file schema in orchestrator cleanup [REQ: state-persistence-for-resume]
- [x] 3.2 Add `last_commit` field to per-change state entries [REQ: state-persistence-for-resume]
- [x] 3.3 Implement state status `"shutdown"` — set during graceful shutdown instead of `"stopped"` [REQ: state-persistence-for-resume]
- [x] 3.4 Collect `last_commit` from each active worktree branch HEAD during shutdown sequence [REQ: state-persistence-for-resume]

## 4. Resume Logic

- [x] 4.1 Add `"shutdown"` status detection in sentinel startup (`fix_stale_state` or new function) [REQ: resume-after-shutdown]
- [x] 4.2 Implement worktree validation: check directory exists, branch HEAD matches `last_commit` [REQ: resume-after-shutdown]
- [x] 4.3 Reset changes with missing/mismatched worktrees to `"pending"` with cleared `worktree_path` [REQ: resume-after-shutdown]
- [x] 4.4 Re-dispatch validated changes with resume context (skip artifact creation) [REQ: resume-after-shutdown]
- [x] 4.5 Log resume actions: which changes resumed vs reset [REQ: resume-after-shutdown]

## 5. E2E Project Directory

- [x] 5.1 Add `--project-dir` flag to `tests/e2e/run.sh` [REQ: persistent-project-directory-for-e2e]
- [x] 5.2 Add `--project-dir` flag to `tests/e2e/run-complex.sh` [REQ: persistent-project-directory-for-e2e]
- [x] 5.3 Update E2E-GUIDE.md with `--project-dir` usage documentation [REQ: persistent-project-directory-for-e2e]

## 6. wt-web API & Settings UI

- [x] 6.1 Add `POST /api/{project}/shutdown` endpoint to `lib/wt_orch/api.py` — reads sentinel PID file, sends SIGUSR1, returns JSON [REQ: shutdown-api-endpoint]
- [x] 6.2 Add `shutdownOrchestration()` function to `web/src/lib/api.ts` [REQ: shutdown-api-endpoint]
- [x] 6.3 Add "Orchestration Control" section to `web/src/pages/Settings.tsx` with Shutdown button + confirmation dialog [REQ: settings-page-shutdown-controls]
- [x] 6.4 Add status badge showing current orchestration state (running/shutdown/stopped) [REQ: settings-page-shutdown-controls]
- [x] 6.5 Add Resume button (visible when status is `"shutdown"`) that calls existing start endpoint [REQ: settings-page-shutdown-controls]

## 7. Tests

- [ ] 7.1 Unit test: `--shutdown` with no running sentinel exits cleanly [REQ: sentinel-graceful-shutdown-command]
- [ ] 7.2 Unit test: wt-loop SIGTERM during idle exits immediately [REQ: agent-graceful-stop-on-sigterm]
- [ ] 7.3 Unit test: wt-loop SIGTERM during work commits WIP and exits [REQ: agent-graceful-stop-on-sigterm]
- [ ] 7.4 Unit test: resume from `"shutdown"` state with valid worktrees [REQ: resume-after-shutdown]
- [ ] 7.5 Unit test: resume with missing worktree resets to pending [REQ: resume-after-shutdown]
- [ ] 7.6 Unit test: `POST /api/{project}/shutdown` returns ok when sentinel running [REQ: shutdown-api-endpoint]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN user runs `wt-sentinel --shutdown` while sentinel is running THEN all agents receive SIGTERM, state updated to `"shutdown"`, sentinel exits 0 [REQ: sentinel-graceful-shutdown-command, scenario: user-triggers-graceful-shutdown]
- [ ] AC-2: WHEN `wt-sentinel --shutdown` with no sentinel running THEN prints "No sentinel running" and exits 0 [REQ: sentinel-graceful-shutdown-command, scenario: shutdown-with-no-running-sentinel]
- [ ] AC-3: WHEN agents don't exit within 60s THEN SIGKILL sent, changes marked `"stalled"` [REQ: sentinel-graceful-shutdown-command, scenario: shutdown-timeout-exceeded]
- [ ] AC-4: WHEN wt-loop receives SIGTERM during task THEN completes iteration, commits WIP, writes last_commit, exits 0 [REQ: agent-graceful-stop-on-sigterm, scenario: agent-receives-sigterm-during-task-execution]
- [ ] AC-5: WHEN wt-loop receives SIGTERM between iterations THEN exits immediately with code 0 [REQ: agent-graceful-stop-on-sigterm, scenario: agent-receives-sigterm-between-iterations]
- [ ] AC-6: WHEN graceful shutdown occurs THEN state has `"shutdown"` status, `shutdown_at` timestamp, per-change `last_commit` [REQ: state-persistence-for-resume, scenario: state-updated-during-graceful-shutdown]
- [ ] AC-7: WHEN sentinel starts with `"shutdown"` state THEN validates worktrees, resumes valid changes, resets invalid to pending [REQ: resume-after-shutdown, scenario: sentinel-starts-with-shutdown-state]
- [ ] AC-8: WHEN resume finds missing worktree THEN resets change to pending, logs warning [REQ: resume-after-shutdown, scenario: resume-with-missing-worktrees]
- [ ] AC-9: WHEN `run.sh --project-dir ~/path` THEN project created at `~/path/minishop-runN` [REQ: persistent-project-directory-for-e2e, scenario: e2e-scaffold-with-custom-directory]
- [ ] AC-10: WHEN `run.sh` without `--project-dir` THEN uses `/tmp/` default [REQ: persistent-project-directory-for-e2e, scenario: e2e-scaffold-without-flag]
- [ ] AC-11: WHEN client sends `POST /api/{project}/shutdown` THEN sentinel receives SIGUSR1, returns `{"ok": true}` [REQ: shutdown-api-endpoint, scenario: shutdown-via-api]
- [ ] AC-12: WHEN user clicks Shutdown in Settings THEN confirmation dialog appears, on confirm calls API, shows spinner [REQ: settings-page-shutdown-controls, scenario: user-clicks-shutdown-in-settings]
- [ ] AC-13: WHEN orchestration status is `"shutdown"` THEN Settings shows status badge and Resume button [REQ: settings-page-shutdown-controls, scenario: settings-page-shows-shutdown-state]
