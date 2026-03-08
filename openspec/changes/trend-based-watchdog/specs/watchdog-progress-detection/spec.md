## ADDED Requirements

### Requirement: Progress-based trend detection for running changes
The watchdog SHALL detect lack of progress by examining completed iterations in the change's loop-state.json, replacing fixed token budget enforcement.

#### Scenario: Spinning detection — consecutive no_op iterations
- **WHEN** a change has 3 or more consecutive completed iterations at the tail of the iterations array
- **AND** all of those iterations have `no_op` equal to `true` AND `commits` equal to `[]`
- **THEN** the watchdog SHALL mark the change as `"failed"`
- **AND** emit a `WATCHDOG_NO_PROGRESS` event with `action: "fail"` and `pattern: "spinning"`
- **AND** log an error: "Watchdog: {change} spinning — {N} consecutive no-op iterations, failing"
- **AND** send a critical notification

#### Scenario: Stuck detection — consecutive iterations without commits
- **WHEN** a change has 3 or more consecutive completed iterations at the tail of the iterations array
- **AND** all of those iterations have `commits` equal to `[]`
- **AND** at least one of those iterations has `no_op` equal to `false`
- **THEN** the watchdog SHALL call `pause_change()` for the change
- **AND** emit a `WATCHDOG_NO_PROGRESS` event with `action: "pause"` and `pattern: "stuck"`
- **AND** log a warning: "Watchdog: {change} stuck — {N} iterations without commits, pausing"
- **AND** send a normal notification

#### Scenario: Minimum iterations required
- **WHEN** a change has fewer than 2 completed iterations in loop-state.json
- **THEN** the watchdog SHALL NOT evaluate progress patterns
- **AND** SHALL return without action

#### Scenario: Progress detected — recent commits exist
- **WHEN** any of the last 3 completed iterations has a non-empty `commits` array
- **THEN** the watchdog SHALL NOT take any progress-based action
- **AND** SHALL return without action

#### Scenario: Loop already done
- **WHEN** the loop-state.json status is `"done"`
- **THEN** the watchdog SHALL NOT evaluate progress patterns
- **AND** SHALL return without action

#### Scenario: Recently resumed change — cooldown after human intervention
- **WHEN** a change was resumed (status transitioned from `"paused"` to `"running"`)
- **AND** the number of completed iterations since the resume is fewer than 3
- **THEN** the watchdog SHALL NOT evaluate progress patterns
- **AND** SHALL return without action
- **NOTE** Implementation: on resume, `resume_change()` stores the current iteration count in `watchdog.progress_baseline`. The progress check only examines iterations with `n` greater than this baseline.

#### Scenario: Done-check guard before action
- **WHEN** the progress check determines an action is needed (pause or fail)
- **THEN** it SHALL re-read loop-state.json status immediately before calling `pause_change()` or `update_change_field("failed")`
- **AND** if the status is `"done"`, it SHALL skip the action and return without side effects
- **NOTE** This guards against the TOCTOU race where Ralph writes done between the initial read and the action.

#### Scenario: Skip if change already failed or paused by escalation
- **WHEN** the progress check runs after the escalation chain in `watchdog_check()`
- **AND** the change's current status in orchestration-state.json is `"failed"`, `"paused"`, or `"waiting:budget"`
- **THEN** the progress check SHALL return without action

#### Scenario: Loop-state file missing or unreadable
- **WHEN** the loop-state.json file does not exist or cannot be parsed
- **THEN** the watchdog SHALL NOT evaluate progress patterns
- **AND** SHALL return without action (other watchdog checks handle missing loop-state)
