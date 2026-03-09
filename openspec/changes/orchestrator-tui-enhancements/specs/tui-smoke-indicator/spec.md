## ADDED Requirements

### Requirement: Smoke gate distinguishes fix from first-pass success
The gate display SHALL distinguish between smoke tests that passed on first attempt and those that required a fix cycle.

#### Scenario: Smoke passed on first attempt
- **WHEN** `smoke_result` is `pass` and `smoke_status` is not `fixed`
- **THEN** the smoke gate displays `S✓`

#### Scenario: Smoke passed after fix
- **WHEN** `smoke_result` is `pass` and (`smoke_fixed` is `true` OR `smoke_status` is `fixed`)
- **THEN** the smoke gate displays `S✓(fix)`

#### Scenario: Smoke failed
- **WHEN** `smoke_result` is `fail`
- **THEN** the smoke gate displays `S✗`
