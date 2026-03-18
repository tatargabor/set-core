# Tasks: sentinel-tab

## 1. Foundation — `.wt/` directory and Python package

- [x] 1.1 Create `lib/wt_orch/sentinel/__init__.py` package with convenience imports [REQ: event-logging-python-api]
- [x] 1.2 Add `.wt/` directory creation utility (mkdir -p + .gitignore append if missing) [REQ: event-logging-python-api]

## 2. Event logging

- [x] 2.1 Implement `SentinelEventLogger` class in `lib/wt_orch/sentinel/events.py` — typed methods for each event type (poll, crash, restart, decision, escalation), atomic JSONL append [REQ: structured-event-logging]
- [x] 2.2 Implement `rotate()` in `lib/wt_orch/sentinel/rotation.py` — move events.jsonl and findings.json to archive/ with date suffix [REQ: event-rotation-on-new-run]
- [x] 2.3 Create `bin/wt-sentinel-log` CLI entry point wrapping the Python API [REQ: event-logging-cli]
- [x] 2.4 Add unit tests for event logger (append, rotate, directory creation) [REQ: structured-event-logging]
- [x] 2.5 Create `bin/wt-sentinel-rotate` CLI entry point wrapping rotation.py [REQ: event-rotation-on-new-run]

## 3. Findings management

- [x] 3.1 Implement `SentinelFindings` class in `lib/wt_orch/sentinel/findings.py` — add, update, list, assess methods with atomic JSON write. `add()` SHALL also emit a `finding` event via `SentinelEventLogger` (depends on 2.1) [REQ: structured-findings-storage]
- [x] 3.2 Create `bin/wt-sentinel-finding` CLI entry point (add, update, list, assess subcommands) [REQ: findings-cli]
- [x] 3.3 Add unit tests for findings (add, update, list filtering, assess, rotation) [REQ: structured-findings-storage]

## 4. Status and inbox

- [x] 4.1 Implement `SentinelStatus` class in `lib/wt_orch/sentinel/status.py` — register, heartbeat, deactivate, get methods [REQ: sentinel-status-registration]
- [x] 4.2 Implement `check_inbox()` in `lib/wt_orch/sentinel/inbox.py` — lightweight file-based inbox read using existing outbox/chat file format [REQ: sentinel-inbox-polling]
- [x] 4.3 Create `bin/wt-sentinel-inbox` CLI (check, ack subcommands) [REQ: sentinel-inbox-polling]
- [x] 4.4 Create `bin/wt-sentinel-status` CLI (register, heartbeat, get subcommands) [REQ: sentinel-status-registration]
- [x] 4.5 Add unit tests for status and inbox [REQ: sentinel-status-registration]

## 5. Integrate with bash sentinel

- [x] 5.1 Modify `bin/wt-sentinel` — replace `emit_event` calls with `wt-sentinel-log` CLI calls. Map legacy event names: SENTINEL_RESTART→restart, SENTINEL_FAILED→escalation, STATE_RECONSTRUCTED→decision [REQ: structured-event-logging]
- [x] 5.2 Modify `bin/wt-sentinel` — split 10s sleep into 2x5s with `wt-sentinel-inbox check` between [REQ: sentinel-inbox-polling]
- [x] 5.3 Modify `bin/wt-sentinel` — add `wt-sentinel-status register` on startup (after ORCH_PID is known, pass --orchestrator-pid) and expand `cleanup()` EXIT trap to call `wt-sentinel-status deactivate` [REQ: sentinel-status-registration]
- [x] 5.4 Modify `bin/wt-sentinel` — add `wt-sentinel-rotate` on new run start (full-reset path only, not partial reset) [REQ: event-rotation-on-new-run]
- [x] 5.5 Add `wt-sentinel-status heartbeat` call after each state poll cycle [REQ: sentinel-status-registration]
- [x] 5.6 Add integration smoke test for bash sentinel — verify events.jsonl written, status.json created on startup, inbox checked during sleep split [REQ: structured-event-logging]

## 6. Integrate with agent sentinel skill

- [x] 6.1 Update `.claude/commands/wt/sentinel.md` — add event logging instructions (call `wt-sentinel-log` on every decision) [REQ: structured-event-logging]
- [x] 6.2 Update `.claude/commands/wt/sentinel.md` — add inbox check instructions (3s interval in poll loop) [REQ: sentinel-inbox-polling]
- [x] 6.3 Update `.claude/commands/wt/sentinel.md` — add status registration on startup (call `wt-sentinel-status register` after ORCH_PID=$! is set, pass --orchestrator-pid) [REQ: sentinel-status-registration]
- [x] 6.5 Update `.claude/commands/wt/sentinel.md` — add heartbeat call (`wt-sentinel-status heartbeat`) after each state poll [REQ: sentinel-status-registration]
- [x] 6.4 Update `.claude/commands/wt/sentinel.md` — add findings instructions (call `wt-sentinel-finding add` when discovering issues) [REQ: structured-findings-storage]

## 7. wt-web backend — REST endpoints

- [x] 7.1 Add `GET /api/{project}/sentinel/events` endpoint — read events.jsonl with `since` timestamp filter. Return `[]` when file does not exist (not 404) [REQ: rest-api-endpoints]
- [x] 7.2 Add `GET /api/{project}/sentinel/findings` endpoint — read findings.json, response includes both `findings` and `assessments` arrays. Return `{"findings":[],"assessments":[]}` when file does not exist [REQ: rest-api-endpoints]
- [x] 7.3 Add `GET /api/{project}/sentinel/status` endpoint — read status.json with computed `is_active` field. Return `{"active":false}` when file does not exist [REQ: rest-api-endpoints]
- [x] 7.4 Add `POST /api/{project}/sentinel/message` endpoint — write to sentinel inbox via outbox file [REQ: rest-api-endpoints]

## 8. wt-web frontend — Sentinel tab

- [x] 8.1 Create `useSentinelData.ts` hook — poll events/findings/status endpoints at 1s interval [REQ: sentinel-tab-in-dashboard]
- [x] 8.2 Create `SentinelPanel.tsx` component — status bar, event stream, findings panel, message input [REQ: sentinel-tab-in-dashboard]
- [x] 8.3 Add event stream view with type-specific color coding and scroll-position-aware auto-scroll (pause auto-scroll when user scrolls up) [REQ: event-stream-display]
- [x] 8.4 Add poll event condensation (collapse consecutive same-state polls) [REQ: event-stream-display]
- [x] 8.5 Add findings panel with severity badges and status indicators [REQ: findings-panel]
- [x] 8.6 Add message input with send button, disabled when sentinel inactive [REQ: message-input]
- [x] 8.7 Register Sentinel tab in Dashboard.tsx (visible when status.json exists) [REQ: sentinel-tab-in-dashboard]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN sentinel polls state THEN poll event with state/change/iteration appended to events.jsonl [REQ: structured-event-logging, scenario: poll-event-emitted]
- [x] AC-2: WHEN orchestrator crashes THEN crash event with pid/exit_code/stderr_tail appended [REQ: structured-event-logging, scenario: crash-event-emitted]
- [x] AC-3: WHEN sentinel restarts orchestrator THEN restart event with new_pid/attempt appended [REQ: structured-event-logging, scenario: restart-event-emitted]
- [x] AC-4: WHEN sentinel makes autonomous decision THEN decision event with action/reason appended [REQ: structured-event-logging, scenario: decision-event-emitted]
- [x] AC-5: WHEN sentinel needs user input THEN escalation event with reason/context appended [REQ: structured-event-logging, scenario: escalation-event-emitted]
- [x] AC-6: WHEN SentinelEventLogger initializes and .wt/ missing THEN .wt/ created and /.wt/ added to .gitignore [REQ: event-logging-python-api, scenario: logger-creates-wt-directory-and-gitignore]
- [x] AC-7: WHEN rotation triggered THEN events.jsonl moved to archive/ with date suffix [REQ: event-rotation-on-new-run, scenario: rotation-moves-old-events-to-archive]
- [x] AC-8: WHEN finding added THEN appended to findings array with auto-generated ID and finding event emitted [REQ: structured-findings-storage, scenario: finding-added]
- [x] AC-9: WHEN finding updated THEN matching entry updated in place [REQ: structured-findings-storage, scenario: finding-updated]
- [x] AC-10: WHEN bash sentinel sleeps THEN sleep split into 2x5s with inbox check between [REQ: sentinel-inbox-polling, scenario: bash-sentinel-inbox-check]
- [x] AC-11: WHEN agent sentinel sleeps THEN sleep split into 10x3s with inbox check between [REQ: sentinel-inbox-polling, scenario: agent-sentinel-inbox-check]
- [x] AC-12: WHEN sentinel starts THEN status.json written with active/member/started_at/pid [REQ: sentinel-status-registration, scenario: sentinel-startup-registration]
- [x] AC-13: WHEN sentinel exits THEN status.json updated with active:false [REQ: sentinel-status-registration, scenario: sentinel-shutdown]
- [x] AC-14: WHEN Dashboard opens and status.json exists THEN Sentinel tab visible [REQ: sentinel-tab-in-dashboard, scenario: tab-visible-when-sentinel-data-exists]
- [x] AC-15: WHEN events displayed THEN each type has distinct color styling [REQ: event-stream-display, scenario: events-rendered-with-type-specific-styling]
- [x] AC-16: WHEN user sends message THEN POST /sentinel/message called and message_sent event appears [REQ: message-input, scenario: send-message]
- [x] AC-17: WHEN sentinel inactive THEN message input disabled with "Sentinel not running" placeholder [REQ: message-input, scenario: send-disabled-when-sentinel-inactive]
