## ADDED Requirements

### Requirement: Change table shows per-change duration
The change table SHALL include a `Dur` column showing how long each change has been running or took to complete.

#### Scenario: Completed change shows final duration
- **WHEN** a change has both `started_at` and `completed_at` timestamps
- **THEN** the `Dur` column displays the duration between them using the standard format (e.g., `21m`, `1h05m`)

#### Scenario: Running change shows live duration
- **WHEN** a change has `started_at` but no `completed_at` and status is `running`
- **THEN** the `Dur` column displays `now() - started_at`, updating every refresh cycle

#### Scenario: Pending or dispatched change shows no duration
- **WHEN** a change has no `started_at` or status is `pending`/`dispatched`
- **THEN** the `Dur` column displays `-`

### Requirement: Summary row at table bottom
The change table SHALL display a summary row as the last row, visually distinct from data rows.

#### Scenario: Summary row content
- **WHEN** at least one change exists in the state
- **THEN** the summary row displays: merged/total count in the Name column, average duration in the Dur column, total billed tokens (input+output) in the token column, and dashes in other columns

#### Scenario: Summary row styling
- **WHEN** the summary row is rendered
- **THEN** it uses dim/bold styling to visually separate it from regular change rows
