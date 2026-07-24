## ADDED Requirements

### Requirement: Named entries can be archived regardless of age or location
The system SHALL provide a command that archives specific registry entries given by name. The
age threshold and E2E-root restriction that govern bulk archiving SHALL NOT apply, because a
named entry involves no selection to constrain.

#### Scenario: A project outside the E2E root, named explicitly
- **WHEN** an operator names a registered project that is not under the E2E run root
- **THEN** it SHALL be archived

#### Scenario: A recent entry, named explicitly
- **WHEN** an operator names an entry younger than any bulk threshold
- **THEN** it SHALL be archived

### Requirement: Named archiving warns about open issues but proceeds
Archiving a named entry that has open issues SHALL report the open-issue count and SHALL
proceed. The bulk archiving path's refusal SHALL remain unchanged.

#### Scenario: Named entry with open issues
- **WHEN** an operator names an entry that has open issues
- **THEN** the entry SHALL be archived and the output SHALL state the open-issue count

#### Scenario: The bulk path still refuses
- **WHEN** bulk archiving encounters an eligible entry with open issues
- **THEN** it SHALL still refuse that entry

### Requirement: Named archiving refuses a live process and a missing directory
Archiving a named entry SHALL be refused, with a reason, when the entry has a live sentinel or
orchestrator process, or when its directory does not exist. There SHALL be no option that
overrides either refusal.

#### Scenario: A running project
- **WHEN** an operator names an entry with a live sentinel or orchestrator PID
- **THEN** the command SHALL refuse it and name the running process

#### Scenario: An entry whose directory is gone
- **WHEN** an operator names an entry whose directory does not exist
- **THEN** the command SHALL refuse it and direct the operator to deregistration instead

### Requirement: An unknown name aborts before any write
When any supplied name is not present in the registry, the command SHALL write nothing at all
— neither for the unknown name nor for the valid ones — and SHALL report which names were not
found.

#### Scenario: One name of several is misspelled
- **WHEN** an operator supplies three names and one does not exist
- **THEN** no entry SHALL be modified and the unknown name SHALL be reported

### Requirement: Unarchiving restores an entry exactly
The system SHALL provide a command that removes the archived marking from named entries,
leaving every other field as it was.

#### Scenario: Round trip
- **WHEN** an entry is archived by name and then unarchived
- **THEN** the entry SHALL be byte-equivalent to its state before archiving

#### Scenario: Unarchiving an entry that is not archived
- **WHEN** an operator unarchives an entry that carries no archived marking
- **THEN** the entry SHALL be left unchanged and the no-op SHALL be reported

### Requirement: Archiving the default project clears and reports the default
When a named entry being archived is the registry's default project, the command SHALL clear
the default pointer and SHALL report that it did so.

#### Scenario: The default is archived
- **WHEN** an operator archives the entry that the registry names as default
- **THEN** the default SHALL be cleared and the output SHALL state that the default was cleared
  and which entry it had named

### Requirement: Named archiving previews and backs up like the bulk path
The named commands SHALL support a preview mode that writes nothing, and SHALL write a
timestamped backup of the registry before any mutation.

#### Scenario: Preview writes nothing
- **WHEN** the named archive command runs in preview mode
- **THEN** the registry's content and modification time SHALL be unchanged and no backup file
  SHALL be created

#### Scenario: Backup precedes mutation
- **WHEN** the named archive command modifies the registry
- **THEN** a timestamped backup holding the pre-command content SHALL exist afterwards
