## ADDED Requirements

### Requirement: Merge operations have a configurable timeout
The `merge_change()` function SHALL enforce a maximum duration via a configurable `merge_timeout` directive (default 1800 seconds).

#### Scenario: Merge completes within timeout
- **WHEN** merge_change completes (including blocking smoke) within the timeout
- **THEN** normal processing continues

#### Scenario: Merge exceeds timeout
- **WHEN** merge_change execution exceeds the configured timeout
- **THEN** the system SHALL release the merge lock, set the change status to `merge_timeout`, and send a sentinel notification

#### Scenario: Merge timeout is configurable
- **WHEN** the orchestration.yaml contains `merge_timeout: <seconds>`
- **THEN** the system SHALL use that value instead of the default 1800 seconds
