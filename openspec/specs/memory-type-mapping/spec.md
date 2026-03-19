## Requirements

### Requirement: CLI maps unsupported memory types to valid shodh-memory types
`set-memory remember` SHALL map unsupported `--type` values to valid shodh-memory types before storage: `Observation` → `Learning`, `Event` → `Context`. A warning SHALL be printed to stderr when mapping occurs.

#### Scenario: Observation type mapped
- **WHEN** user runs `echo "insight" | set-memory remember --type Observation --tags test`
- **THEN** the memory is stored with `experience_type: Learning`
- **AND** stderr contains a warning: `Note: type 'Observation' mapped to 'Learning'`

#### Scenario: Event type mapped
- **WHEN** user runs `echo "done" | set-memory remember --type Event --tags test`
- **THEN** the memory is stored with `experience_type: Context`
- **AND** stderr contains a warning: `Note: type 'Event' mapped to 'Context'`

#### Scenario: Valid types pass through unchanged
- **WHEN** user runs `echo "x" | set-memory remember --type Decision --tags test`
- **THEN** the memory is stored with `experience_type: Decision`
- **AND** no mapping warning is printed

### Requirement: Valid memory types are documented
The CLI help text (`set-memory --help`) SHALL list the 3 valid shodh-memory types: `Decision`, `Learning`, `Context`.

#### Scenario: Help text shows valid types
- **WHEN** user runs `set-memory --help`
- **THEN** output includes the valid types and mapping note

### Requirement: GUI shows only valid memory types
The RememberNoteDialog type selector SHALL offer only `Learning`, `Decision`, `Context`. The MemoryBrowseDialog SHALL use badge colors for these 3 types only.

#### Scenario: Remember dialog type options
- **WHEN** user opens the Remember Note dialog
- **THEN** the type dropdown contains exactly: Learning, Decision, Context

#### Scenario: Browse dialog renders badge for each type
- **WHEN** a memory with experience_type Learning is displayed
- **THEN** the badge shows "Learning" with green color
- **WHEN** a memory with experience_type Decision is displayed
- **THEN** the badge shows "Decision" with blue color
- **WHEN** a memory with experience_type Context is displayed
- **THEN** the badge shows "Context" with amber color
