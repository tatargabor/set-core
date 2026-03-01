## ADDED Requirements

### Requirement: Plan JSON skip_review field
Each change in the plan JSON MAY include a `skip_review` boolean field. When `true`, the verify gate SHALL skip code review for that change. Default SHALL be `false`.

#### Scenario: Doc-only change skips review
- **WHEN** a change has `"skip_review": true` and completes implementation
- **THEN** the verify gate SHALL not run the code review step
- **AND** `review_result` SHALL be set to `"skipped"`

#### Scenario: Normal change gets review
- **WHEN** a change has `"skip_review": false` (or not set) and `review_before_merge` is `true`
- **THEN** the verify gate SHALL run code review as normal

### Requirement: Plan JSON skip_test field
Each change in the plan JSON MAY include a `skip_test` boolean field. When `true`, the verify gate SHALL skip test execution for that change. Default SHALL be `false`.

#### Scenario: Doc-only change skips tests
- **WHEN** a change has `"skip_test": true` and completes implementation
- **THEN** the verify gate SHALL not run the test command
- **AND** `test_result` SHALL be set to `"skipped"`

#### Scenario: Normal change runs tests
- **WHEN** a change has `"skip_test": false` (or not set) and a `test_command` is configured
- **THEN** the verify gate SHALL run tests as normal

### Requirement: State initialization carries gate skip fields
`init_state()` SHALL carry `skip_review` and `skip_test` from the plan JSON into the state JSON for each change, defaulting to `false` when not present.

#### Scenario: Fields preserved in state
- **WHEN** a plan JSON change has `"skip_review": true, "skip_test": true`
- **THEN** the state JSON for that change SHALL contain both fields with value `true`

#### Scenario: Fields default to false
- **WHEN** a plan JSON change has no `skip_review` or `skip_test` fields
- **THEN** the state JSON SHALL contain `"skip_review": false, "skip_test": false`

### Requirement: TUI displays skipped gate results
The orchestrator status display SHALL show `"skip"` in the Tests and Review columns when the respective gate step was skipped.

#### Scenario: Status shows skipped test
- **WHEN** a change has `test_result: "skipped"`
- **THEN** the TUI SHALL display `"skip"` in the Tests column
