## ADDED Requirements

### Requirement: Merge retry ceiling configurable and raised
The merge retry ceiling (`MAX_MERGE_RETRIES`) SHALL be exposed as a directive `max_merge_retries`, with default raised from 3 to 5. The `MAX_MERGE_RETRIES` module-level constant SHALL remain as a backward-compatible alias bound to the directive's default.

#### Scenario: Operator overrides max_merge_retries
- **WHEN** an operator sets `max_merge_retries: 7` in `orchestration.yaml`
- **THEN** the merger uses 7 as the ceiling for the run
- **AND** retries beyond 7 result in `failed:merge_retries_exhausted`

#### Scenario: Default ceiling is 5 without override
- **WHEN** no override is provided
- **THEN** the merger uses 5 as the ceiling
- **AND** `MAX_MERGE_RETRIES` import returns 5
