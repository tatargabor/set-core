## ADDED Requirements

### Requirement: Test done criteria runs test command
The loop system SHALL support `done_criteria = "test"` in `is_done()`. When active, `_check_test_done()` SHALL run the project's test command and return True if tests pass (exit code 0), False otherwise.

#### Scenario: Test command passes
- **WHEN** `is_done("test")` is called and the test command exits with code 0
- **THEN** the function SHALL return True

#### Scenario: Test command fails
- **WHEN** `is_done("test")` is called and the test command exits with non-zero code
- **THEN** the function SHALL return False

#### Scenario: Test command times out
- **WHEN** the test command does not complete within 300 seconds
- **THEN** `_check_test_done()` SHALL return False

### Requirement: Test command resolution fallback chain
`_check_test_done()` SHALL resolve the test command using a three-level fallback chain:
1. `test_command` field from `loop-state.json` (passed via `--test-command` flag)
2. `config.auto_detect_test_command(wt_path)` (profile → legacy detection)
3. Fall back to `_check_build_done(wt_path)` as last resort

#### Scenario: Test command from loop state
- **WHEN** `loop-state.json` contains a `test_command` field
- **THEN** that command SHALL be used for the test check

#### Scenario: Test command from auto-detect
- **WHEN** `loop-state.json` has no `test_command` field
- **AND** `config.auto_detect_test_command()` returns a non-empty string
- **THEN** the auto-detected command SHALL be used

#### Scenario: No test command available — build fallback
- **WHEN** neither loop state nor auto-detect provides a test command
- **THEN** `_check_build_done(wt_path)` SHALL be used as fallback

### Requirement: Test command runs as shell string
The test command SHALL be executed via `subprocess.run(cmd, shell=True, cwd=wt_path)`, not decomposed into package manager + script name. This matches how the verifier runs test commands.

#### Scenario: Complex test command
- **WHEN** the test command is `pnpm test -- --reporter=dot`
- **THEN** it SHALL be passed to the shell as-is, not parsed into components

### Requirement: wt-loop accepts --test-command flag
`wt-loop start` SHALL accept an optional `--test-command <cmd>` argument. When provided, the command SHALL be stored in `loop-state.json` under the `test_command` key.

#### Scenario: Flag provided
- **WHEN** `wt-loop start "task" --done test --test-command "pnpm test"`
- **THEN** `loop-state.json` SHALL contain `"test_command": "pnpm test"`

#### Scenario: Flag omitted
- **WHEN** `wt-loop start "task" --done test` without `--test-command`
- **THEN** `loop-state.json` SHALL contain `"test_command": null`
- **AND** `_check_test_done()` SHALL treat `null` as absent and proceed to auto-detect fallback
