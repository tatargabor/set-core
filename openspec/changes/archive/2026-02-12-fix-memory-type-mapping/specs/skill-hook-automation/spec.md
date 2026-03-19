## ADDED Requirements

### Requirement: Memory hooks use only valid shodh-memory types
All `set-memory remember --type` invocations in hook templates SHALL use valid shodh-memory types: `Decision`, `Learning`, or `Context`. The hooks SHALL NOT use `Observation` or `Event`.

#### Scenario: Archive hook saves completion record
- **WHEN** the archive hook saves a change completion event
- **THEN** it uses `--type Context` (not `--type Event`)

#### Scenario: Apply hook saves error observations
- **WHEN** the apply hook saves error descriptions
- **THEN** it uses `--type Learning` (not `--type Observation`)

#### Scenario: Hooks reinstalled after update
- **WHEN** `set-memory-hooks install` is run after the type mapping fix
- **THEN** all installed SKILL.md files contain only valid types
