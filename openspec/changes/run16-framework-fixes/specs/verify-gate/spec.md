## MODIFIED Requirements

### Requirement: Verify gate results SHALL be preserved across monitor restart
When the monitor restarts (crash recovery or manual restart), it SHALL check for changes in "verifying" status that already have all blocking gates passed. Such changes SHALL proceed to merge instead of being re-dispatched.

#### Scenario: Monitor dies after verify passes but before merge
- **WHEN** a change has status "verifying"
- **AND** all blocking verify gates have result "pass" or "skipped" (test_result, build_result, review_result, scope_result)
- **AND** the monitor restarts and polls active changes
- **THEN** the monitor SHALL proceed to merge the change
- **AND** the monitor SHALL NOT re-dispatch a retry agent

#### Scenario: Change in verifying with incomplete gates after restart
- **WHEN** a change has status "verifying"
- **AND** one or more blocking gates have no result (empty/null)
- **AND** the monitor restarts
- **THEN** the monitor SHALL re-run the verify gate from the beginning
