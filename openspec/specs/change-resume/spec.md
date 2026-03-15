## ADDED Requirements

### Requirement: resume_change passes test command to loop
`resume_change()` SHALL resolve the test command and pass it to `wt-loop start` via `--test-command <cmd>` when `done_criteria` is `"test"`.

#### Scenario: Test command from directives
- **WHEN** `resume_change()` triggers a review retry
- **AND** `directives.test_command` is set in orchestration state extras
- **THEN** `wt-loop start` SHALL be called with `--test-command "<directives.test_command>"`

#### Scenario: Test command from auto-detect
- **WHEN** `resume_change()` triggers a review retry
- **AND** `directives.test_command` is not set
- **THEN** `resume_change()` SHALL call `config.auto_detect_test_command(wt_path)`
- **AND** pass the result via `--test-command` if non-empty

#### Scenario: No test command available
- **WHEN** neither directives nor auto-detect provide a test command
- **THEN** `resume_change()` SHALL NOT pass `--test-command` to `wt-loop`
- **AND** `_check_test_done()` SHALL fall back to build check (per test-done-criteria spec)

### Requirement: Loop state stores test command
When `--test-command` is provided to `wt-loop start`, the command SHALL be persisted in `loop-state.json` under the `test_command` key so that `_check_test_done()` can read it on each iteration.

#### Scenario: Test command persisted in loop state
- **WHEN** `wt-loop start "fix" --done test --test-command "pytest -x"`
- **THEN** `loop-state.json` SHALL contain `"test_command": "pytest -x"`
- **AND** `_check_test_done()` SHALL read this value on each done check
