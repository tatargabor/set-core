## ADDED Requirements

### Requirement: Retired framework artifacts are not deployed and are removed
The deploy manifest SHALL carry a retired list. An artifact on it SHALL NOT be deployed, and
a copy that an earlier deploy wrote — as recorded in the deploy ledger with an unchanged hash —
SHALL be removed by the next `set-project init`. A copy whose hash differs from the ledger's
SHALL be kept and reported, never removed.

#### Scenario: A retired command deployed earlier
- **WHEN** a consumer holds an unchanged copy of a slash command that is now retired
- **THEN** `set-project init` removes it and reports it under "retired"

#### Scenario: A retired file the consumer edited
- **WHEN** the consumer's copy of a retired file differs from the hash the ledger recorded
- **THEN** the file stays, and the run reports it as "retired, locally modified — kept"

#### Scenario: The dry-run shows the removal
- **WHEN** `set-project init --dry-run` runs in a project holding retired copies
- **THEN** the plan lists each removal and nothing is written
