## 1. Dispatcher PID Validation

- [x] 1.1 Replace bare `pass` in PID extraction except block with `logger.error()` that logs the exception details [REQ: dispatch-pid-validation]
- [x] 1.2 After PID extraction, validate `terminal_pid > 0` — if not, mark change as "failed", log error, and return False [REQ: dispatch-pid-validation]

## 2. Watchdog Null-PID Fast-Path

- [x] 2.1 Add early check in `watchdog_check()` before timeout/loop detection: if status is "running" and `ralph_pid` is 0/null, immediately set `should_escalate = True` with descriptive reason [REQ: watchdog-null-pid-fast-path]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN loop-state.json contains a valid terminal_pid THEN change is marked "running" with correct ralph_pid [REQ: dispatch-pid-validation, scenario: valid-pid-in-loop-state-json]
- [x] AC-2: WHEN loop-state.json lacks terminal_pid field THEN dispatcher marks change "failed" and logs error [REQ: dispatch-pid-validation, scenario: missing-terminal-pid-field]
- [x] AC-3: WHEN loop-state.json has terminal_pid: null THEN dispatcher marks change "failed" and logs error [REQ: dispatch-pid-validation, scenario: null-terminal-pid-value]
- [x] AC-4: WHEN loop-state.json contains invalid JSON THEN dispatcher marks change "failed" and logs parse error [REQ: dispatch-pid-validation, scenario: json-parse-failure]
- [x] AC-5: WHEN watchdog checks running change with ralph_pid=0 THEN immediate escalation with invalid-PID reason [REQ: watchdog-null-pid-fast-path, scenario: running-change-with-zero-pid]
- [x] AC-6: WHEN watchdog checks running change with valid PID THEN normal timeout/loop logic applies [REQ: watchdog-null-pid-fast-path, scenario: running-change-with-valid-pid]
