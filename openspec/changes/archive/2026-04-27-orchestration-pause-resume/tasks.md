# Tasks: orchestration-pause-resume

## 1. Ralph Graceful Iteration Stop

- [x] 1.1 In `lib/loop/engine.sh`: add `SHUTDOWN_REQUESTED=0` flag and modify SIGTERM trap to set it [REQ: ralph-graceful-iteration-stop]
- [x] 1.2 In `lib/loop/engine.sh`: modify main loop to check `SHUTDOWN_REQUESTED` before each new iteration [REQ: ralph-graceful-iteration-stop]
- [x] 1.3 In `lib/loop/engine.sh`: extend `cleanup_on_exit` to kill child processes (`pkill -P $$`, 10s grace, then `pkill -9 -P $$`) [REQ: ralph-graceful-iteration-stop]

## 2. Shutdown Cascade & Progress Events

- [x] 2.1 In `lib/set_orch/engine.py` `cleanup_orchestrator()`: iterate Ralph PIDs from state, send SIGTERM to each [REQ: graceful-shutdown-cascade]
- [x] 2.2 In `lib/set_orch/engine.py`: emit `SHUTDOWN_STARTED` event with list of active changes before sending signals [REQ: graceful-shutdown-cascade]
- [x] 2.3 In `lib/set_orch/engine.py`: emit `CHANGE_STOPPING` event for each Ralph PID before sending SIGTERM [REQ: graceful-shutdown-cascade]
- [x] 2.4 In `lib/set_orch/engine.py`: wait for each Ralph PID (up to 90s total), emit `CHANGE_STOPPED` event as each exits [REQ: graceful-shutdown-cascade]
- [x] 2.5 In `lib/set_orch/engine.py`: SIGKILL any Ralph PIDs still alive after 90s timeout [REQ: graceful-shutdown-cascade]
- [x] 2.6 In `lib/set_orch/engine.py`: emit `SHUTDOWN_COMPLETE` event with total duration after all processes stopped [REQ: graceful-shutdown-cascade]
- [x] 2.7 Set change status to "paused" for each change whose Ralph was stopped during shutdown (so they resume on restart) [REQ: graceful-shutdown-cascade]

## 3. Start/Resume API Endpoint

- [x] 3.1 Add `POST /api/{project}/start` endpoint in `lib/set_orch/api.py` [REQ: start-endpoint-spawns-sentinel]
- [x] 3.2 Implement sentinel PID liveness check — return 409 if already running [REQ: start-endpoint-spawns-sentinel]
- [x] 3.3 Resolve spec path: check state `extras.spec_path` → `wt/orchestration/config.yaml` spec key → fallback patterns [REQ: start-endpoint-spawns-sentinel]
- [x] 3.4 Handle corrupt state file — return 500 with detail message [REQ: start-endpoint-spawns-sentinel]
- [x] 3.5 Spawn `set-sentinel --spec <path>` via `subprocess.Popen(start_new_session=True)` in project directory [REQ: start-endpoint-spawns-sentinel]
- [x] 3.6 Return `{ok: true, pid: <sentinel_pid>}` on success [REQ: start-endpoint-spawns-sentinel]

## 4. Per-Change Pause/Resume API

- [x] 4.1 Add `POST /api/{project}/changes/{name}/pause` endpoint [REQ: per-change-pause-and-resume]
- [x] 4.2 Pause endpoint: validate change is in pausable state ("running"); return 409 for non-pausable states, 200 for already "paused" (idempotent) [REQ: per-change-pause-and-resume]
- [x] 4.3 Pause endpoint: send SIGTERM to change's `ralph_pid`, set change status to "paused" [REQ: per-change-pause-and-resume]
- [x] 4.4 Add `POST /api/{project}/changes/{name}/resume` endpoint [REQ: per-change-pause-and-resume]
- [x] 4.5 Resume endpoint: validate change is "paused"; return 200 for already "running" (idempotent), 409 for other states [REQ: per-change-pause-and-resume]
- [x] 4.6 Resume endpoint: check max_parallel — if at capacity return 429 with message [REQ: per-change-pause-and-resume]
- [x] 4.7 Resume endpoint: set change status to "dispatched" so the monitor loop re-dispatches a new Ralph loop [REQ: per-change-pause-and-resume]

## 5. Frontend — Resume & Status Fixes

- [x] 5.1 In `web/src/pages/Settings.tsx`: show Resume button for both "stopped" and "shutdown" states [REQ: frontend-shows-resume-for-resumable-states]
- [x] 5.2 Differentiate labels: "Paused (clean shutdown)" with green styling for "shutdown", "Stopped (unexpected)" with amber styling for "stopped" [REQ: frontend-shows-resume-for-resumable-states]
- [x] 5.3 Add `startOrchestration()` function in `web/src/lib/api.ts` calling `POST /api/{project}/start` [REQ: start-endpoint-spawns-sentinel]
- [x] 5.4 Wire Resume button to call `startOrchestration()` instead of raw fetch [REQ: start-endpoint-spawns-sentinel]

## 6. Frontend — Per-Change Pause/Resume

- [x] 6.1 Add `pauseChange(project, name)` and `resumeChange(project, name)` in `web/src/lib/api.ts` [REQ: per-change-pause-and-resume]
- [x] 6.2 Add Pause button on running change cards in Dashboard [REQ: per-change-pause-and-resume]
- [x] 6.3 Add Resume button on paused change cards in Dashboard [REQ: per-change-pause-and-resume]
- [x] 6.4 Handle 429 (max parallel) on resume — show toast/message to user [REQ: per-change-pause-and-resume]

## 7. Frontend — Shutdown Progress Panel

- [x] 7.1 Create `web/src/components/ShutdownProgress.tsx` component [REQ: frontend-shows-resume-for-resumable-states]
- [x] 7.2 Parse SHUTDOWN_STARTED/CHANGE_STOPPING/CHANGE_STOPPED/SHUTDOWN_COMPLETE events from sentinel event stream [REQ: frontend-shows-resume-for-resumable-states]
- [x] 7.3 Render process list: each line shows change name + status icon (spinner=stopping, checkmark=stopped, warning=timed out) [REQ: frontend-shows-resume-for-resumable-states]
- [x] 7.4 Show panel on Dashboard when shutdown is in progress; hide after SHUTDOWN_COMPLETE or 30s of no events [REQ: frontend-shows-resume-for-resumable-states]
- [x] 7.5 Detect stale shutdown (no events for 30s) and show "Shutdown may have stalled" warning [REQ: frontend-shows-resume-for-resumable-states]

## 8. Build & Test

- [x] 8.1 Rebuild web frontend (`cd web && npm run build`) [REQ: frontend-shows-resume-for-resumable-states]
- [ ] 8.2 Manual test: start orchestration from web dashboard, verify sentinel spawns [REQ: start-endpoint-spawns-sentinel]
- [ ] 8.3 Manual test: shutdown from web, verify progress panel shows, Ralph stops after current iteration [REQ: graceful-shutdown-cascade]
- [ ] 8.4 Manual test: resume from web after shutdown, verify orchestration continues [REQ: start-endpoint-spawns-sentinel]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN project status is "shutdown" and user calls POST /start THEN sentinel spawns and resumes [REQ: start-endpoint-spawns-sentinel, scenario: start-from-shutdown-state]
- [x] AC-2: WHEN project status is "stopped" and user calls POST /start THEN sentinel recovers and resumes [REQ: start-endpoint-spawns-sentinel, scenario: start-from-stopped-state]
- [x] AC-3: WHEN sentinel already running and user calls POST /start THEN 409 returned [REQ: start-endpoint-spawns-sentinel, scenario: start-when-already-running]
- [x] AC-4: WHEN state file is corrupt and user calls POST /start THEN 500 with detail [REQ: start-endpoint-spawns-sentinel, scenario: start-with-corrupt-state-file]
- [x] AC-5: WHEN Ralph receives SIGTERM during iteration THEN it finishes iteration, commits WIP, exits [REQ: ralph-graceful-iteration-stop, scenario: sigterm-during-active-iteration]
- [x] AC-6: WHEN Ralph receives SIGTERM between iterations THEN exits immediately [REQ: ralph-graceful-iteration-stop, scenario: sigterm-between-iterations]
- [x] AC-7: WHEN Ralph exits with child processes THEN children get SIGTERM, 10s grace, then SIGKILL [REQ: ralph-graceful-iteration-stop, scenario: child-process-cleanup-on-ralph-exit]
- [x] AC-8: WHEN graceful shutdown in progress THEN events emitted: SHUTDOWN_STARTED → CHANGE_STOPPING → CHANGE_STOPPED → SHUTDOWN_COMPLETE [REQ: graceful-shutdown-cascade, scenario: orchestrator-emits-shutdown-progress-events]
- [x] AC-9: WHEN orchestrator crashes THEN status is "stopped" not "shutdown" [REQ: graceful-shutdown-cascade, scenario: crash-sets-stopped-status]
- [x] AC-10: WHEN status is "shutdown" THEN green Resume button with "Paused (clean shutdown)" label [REQ: frontend-shows-resume-for-resumable-states, scenario: resume-button-for-shutdown-state]
- [x] AC-11: WHEN status is "stopped" THEN amber Resume button with "Stopped (unexpected)" label [REQ: frontend-shows-resume-for-resumable-states, scenario: resume-button-for-stopped-state]
- [x] AC-12: WHEN shutdown in progress THEN Dashboard shows progress panel with per-process status [REQ: frontend-shows-resume-for-resumable-states, scenario: shutdown-progress-list]
- [x] AC-13: WHEN user pauses running change THEN Ralph gets SIGTERM and change becomes "paused" [REQ: per-change-pause-and-resume, scenario: pause-a-running-change]
- [x] AC-14: WHEN user resumes paused change THEN new Ralph dispatched, change becomes "running" [REQ: per-change-pause-and-resume, scenario: resume-a-paused-change]
- [x] AC-15: WHEN resume at max parallel THEN 429 returned [REQ: per-change-pause-and-resume, scenario: resume-when-at-max-parallel-capacity]
- [x] AC-16: WHEN pause already paused change THEN 200 idempotent [REQ: per-change-pause-and-resume, scenario: pause-an-already-paused-change]
- [x] AC-17: WHEN resume already running change THEN 200 idempotent [REQ: per-change-pause-and-resume, scenario: resume-an-already-running-change]
- [x] AC-18: WHEN pause non-running change THEN 409 [REQ: per-change-pause-and-resume, scenario: pause-a-non-running-change]
