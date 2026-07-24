# project-status-api Specification

## Purpose
TBD - created by archiving change consumer-status-contract. Update Purpose after archive.
## Requirements
### Requirement: A command name arriving from a URL never reaches a shell unvalidated
The API SHALL validate a requested command against the project's declared list, and where
no list exists, against a name shape that cannot produce a flag.

#### Scenario: An argument-shaped name
- **WHEN** a requested name could be read as a flag
- **THEN** the request SHALL be refused before anything is spawned

#### Scenario: An undeclared name
- **WHEN** a requested name is not in the declared read list
- **THEN** the API SHALL answer not-found rather than attempt it

### Requirement: A page load runs the declared read commands, and only those
The API SHALL run every declared read command that is not on-demand, and SHALL report
which ones could not be answered.

#### Scenario: One command fails
- **WHEN** one command fails and others succeed
- **THEN** the response SHALL carry the successful answers AND an explicit record of the
  gap with its reason, so that "we could not ask" is distinguishable from "the answer is
  none"

### Requirement: An answer may be held briefly in memory and nowhere else
The API MAY cache an answer in process for a few seconds so that a polling dashboard does
not respawn a project's toolchain on every poll, and SHALL NOT cache to disk.

#### Scenario: A failing contract under polling
- **WHEN** a command fails
- **THEN** the failure SHALL be cached on the same terms as a success, so one defect does
  not become load

#### Scenario: The reader can bypass it
- **WHEN** a caller asks for a refresh
- **THEN** the cache SHALL be bypassed

### Requirement: A write is only ever a request to the project to record something
The write endpoint SHALL accept only commands declared in the project's write list, SHALL
NOT cache, and SHALL drop the project's read cache after a successful write.

#### Scenario: A read command sent to the write endpoint
- **WHEN** a caller sends a declared READ command to the write path
- **THEN** it SHALL be refused

#### Scenario: set-core never originates the state
- **WHEN** a write succeeds
- **THEN** set-core SHALL hold no record of having sent it, since the project owns the
  state and the write is idempotent

