# Tasks: Observability Logging Overhaul

## 1. Critical — Zero-logging Python files (state, sentinel, loop)

- [x] 1.1 Add logging to `lib/set_orch/state.py` — state mutations (update_state_field, update_change_field), lock acquire/release (locked_state), crash recovery, phase transitions, dependency cascade [REQ: state-mutation-logging]
- [x] 1.2 Add logging to `lib/set_orch/sentinel/findings.py` — finding add/update/assess operations with severity and summary [REQ: sentinel-operation-logging]
- [x] 1.3 Add logging to `lib/set_orch/sentinel/status.py` — register, heartbeat, deactivate with session context [REQ: sentinel-operation-logging]
- [x] 1.4 Add logging to `lib/set_orch/sentinel/events.py` — all event emission methods (poll, crash, restart, decision, escalation, finding, message) [REQ: sentinel-operation-logging]
- [x] 1.5 Add logging to `lib/set_orch/loop_tasks.py` — find_tasks_file search path, check_completion progress, is_done decisions, fallback task generation [REQ: loop-task-logging]
- [x] 1.6 Add logging to `lib/set_orch/loop_state.py` — init/read/update state, add_iteration, add_tokens, write_activity [REQ: loop-state-logging]
- [x] 1.7 Add logging to `lib/set_orch/process.py` — check_pid results, safe_kill actions, find_orphans discoveries [REQ: process-lifecycle-logging]

## 2. Critical — Zero-logging Python files (profile, reporter, paths)

- [x] 2.1 Add logging to `lib/set_orch/profile_types.py` — key ABC method calls in CoreProfile/NullProfile (detect_test_command, detect_build_command, detect_e2e_command, get_verification_rules, bootstrap_worktree) [REQ: profile-system-logging]
- [x] 2.2 Add logging to `lib/set_orch/reporter.py` — report generation start/complete, data aggregation steps [REQ: orchestration-observability]

## 3. Partial coverage — Increase log density

- [x] 3.1 Add logging to `lib/set_orch/gate_runner.py` — gate order resolution details, skip/warn/block decisions with reasons, retry context building [REQ: gate-execution-logging]
- [x] 3.2 Add logging to `lib/set_orch/test_coverage.py` — test binding algorithm (exact vs fuzzy match), unbound tests, cross-cutting assignment, coverage summary [REQ: test-coverage-binding-logging]
- [x] 3.3 Add logging to `lib/set_orch/watchdog.py` — escalation level changes, hash ring updates, progress baseline tracking, timeout calculations [REQ: watchdog-detail-logging]
- [x] 3.4 Add logging to `lib/set_orch/planner.py` — requirement processing flow, validation error details, domain decomposition decisions [REQ: orchestration-observability]
- [x] 3.5 Add logging to `lib/set_orch/dispatcher.py` — scope verification, change state transition reasoning, worktree bootstrap outcomes [REQ: orchestration-observability]

## 4. Bash scripts — Add logging to silent operational scripts

- [x] 4.1 Add logging to `bin/set-cleanup`, `bin/set-compare`, `bin/set-core`, `bin/set-deploy-hooks` — source set-common.sh, add log_info for key operations [REQ: bash-script-logging]
- [x] 4.2 Add logging to `bin/set-design-sync`, `bin/set-harvest`, `bin/set-usage`, `bin/set-version` — source set-common.sh, add log_info for key operations [REQ: bash-script-logging]
- [x] 4.3 Add logging to `bin/set-sentinel-finding`, `bin/set-sentinel-status`, `bin/set-sentinel-inbox`, `bin/set-sentinel-log` — source set-common.sh, add log_info for key operations [REQ: bash-script-logging]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a change status is updated THEN state.py logs at INFO with field, old value, new value [REQ: state-mutation-logging, scenario: change-status-transition]
- [x] AC-2: WHEN a state lock is acquired or released THEN state.py logs at DEBUG [REQ: state-mutation-logging, scenario: lock-acquisition-and-release]
- [x] AC-3: WHEN crash recovery fixes stale state THEN state.py logs at WARNING [REQ: state-mutation-logging, scenario: crash-recovery]
- [x] AC-4: WHEN a sentinel finding is recorded THEN findings.py logs at INFO [REQ: sentinel-operation-logging, scenario: finding-created]
- [x] AC-5: WHEN a sentinel heartbeat is emitted THEN status.py logs at DEBUG [REQ: sentinel-operation-logging, scenario: sentinel-heartbeat]
- [x] AC-6: WHEN a sentinel event is emitted THEN events.py logs at INFO [REQ: sentinel-operation-logging, scenario: sentinel-event-emitted]
- [x] AC-7: WHEN find_tasks_file() searches THEN loop_tasks.py logs search paths and result [REQ: loop-task-logging, scenario: task-file-search]
- [x] AC-8: WHEN check_completion() runs THEN loop_tasks.py logs completed/total [REQ: loop-task-logging, scenario: task-completion-check]
- [x] AC-9: WHEN check_pid() runs THEN process.py logs PID status [REQ: process-lifecycle-logging, scenario: pid-check]
- [x] AC-10: WHEN safe_kill() terminates a process THEN process.py logs PID and signal [REQ: process-lifecycle-logging, scenario: process-kill]
- [x] AC-11: WHEN gate order is resolved THEN gate_runner.py logs the ordered list [REQ: gate-execution-logging, scenario: gate-order-resolved]
- [x] AC-12: WHEN a gate is skipped/warned/blocked THEN gate_runner.py logs the decision and reason [REQ: gate-execution-logging, scenario: gate-skip-or-warn]
- [x] AC-13: WHEN a test is bound by exact match THEN test_coverage.py logs at DEBUG [REQ: test-coverage-binding-logging, scenario: deterministic-binding]
- [x] AC-14: WHEN a test cannot be bound THEN test_coverage.py logs at WARNING [REQ: test-coverage-binding-logging, scenario: unbound-test]
- [x] AC-15: WHEN watchdog changes escalation level THEN watchdog.py logs old and new level [REQ: watchdog-detail-logging, scenario: escalation-level-change]
