## IN SCOPE
- Persist sentinel spec hash to disk to survive restarts
- Require approval before resetting orchestration state
- Add --auto-approve-reset flag for unattended runs

## OUT OF SCOPE
- Changing the sentinel monitoring loop
- Modifying orchestration state format

### Requirement: Sentinel persists spec hash
The sentinel SHALL persist the last-seen spec hash to `sentinel-state.json` in the run directory. On restart, it SHALL read the persisted hash instead of defaulting to "unknown."

#### Scenario: Sentinel restart preserves hash
- **GIVEN** sentinel ran with spec hash "abc123"
- **AND** sentinel-state.json contains `{"spec_hash": "abc123"}`
- **WHEN** sentinel restarts
- **THEN** it SHALL read "abc123" from disk, not default to "unknown"
- **AND** it SHALL NOT detect a spec change

### Requirement: Reset requires approval
When the sentinel detects a spec hash change, it SHALL write a `.sentinel-reset-pending` marker file and wait for approval before resetting. If no approval arrives within 5 minutes, it SHALL continue without reset (preserving existing state).

#### Scenario: Spec actually changed, operator approves
- **GIVEN** spec hash changed from "abc" to "def"
- **WHEN** sentinel detects the change
- **THEN** it SHALL write `.sentinel-reset-pending` with reason
- **AND** wait for `.sentinel-approve-reset` file
- **WHEN** operator creates the approval file
- **THEN** sentinel SHALL reset and start fresh

#### Scenario: No approval within timeout
- **GIVEN** spec hash changed
- **WHEN** no approval arrives within 5 minutes
- **THEN** sentinel SHALL continue with existing state (no reset)
- **AND** log a warning about skipped reset

### Requirement: Auto-approve flag for unattended runs
The `--auto-approve-reset` flag SHALL skip the approval gate and auto-reset (preserving current behavior for CI/unattended runs).

#### Scenario: Unattended run with auto-approve
- **GIVEN** sentinel started with `--auto-approve-reset`
- **WHEN** spec hash change detected
- **THEN** sentinel SHALL reset immediately without waiting for approval
