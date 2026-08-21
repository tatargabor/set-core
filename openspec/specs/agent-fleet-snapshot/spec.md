# agent-fleet-snapshot Specification

## Purpose
TBD - created by archiving change fleet-agent-restore. Update Purpose after archive.

## Requirements

### Requirement: The framework records each discovered agent durably, keyed on session identity

The framework SHALL persist, for every interactive agent discovery reports, an entry
carrying its session id, its label or name, its `cwd`, its project, its kind, the time it
was first recorded and the time it was last seen. The entry SHALL be keyed on the **session
id**, never on the pid: a pid is reused, so a pid-keyed record cannot survive the reboot
this capability exists for.

An agent discovery reports without a session id SHALL be recorded as an entry that states
the session id is absent, rather than being dropped — a session alive and unknown to the
runtime's records is a measured condition, and omitting it would make the record claim a
smaller fleet than existed.

#### Scenario: A discovered agent is recorded

- **WHEN** discovery reports an interactive agent with session id `S`, label `L` and cwd `C`
- **THEN** the record for that project contains an entry keyed `S` carrying `L`, `C`, its kind, a first-seen time and a last-seen time

#### Scenario: Seeing the same session again updates last-seen and never duplicates

- **WHEN** discovery reports session id `S` again, at a later time, possibly under a different pid
- **THEN** the existing entry's last-seen time advances, its first-seen time is unchanged, and exactly one entry for `S` exists

#### Scenario: An agent without a session id is recorded as such

- **WHEN** discovery reports an interactive agent that has no session id
- **THEN** an entry exists for it whose session id is explicitly absent, and it is not silently dropped

#### Scenario: One-shot subprocesses are not recorded

- **WHEN** discovery reports an agent whose kind is `oneshot`
- **THEN** no entry is written for it

### Requirement: The record survives the loss of every live process

The record SHALL be stored durably under the framework's per-user store and SHALL be
readable when no process it describes is running. Reading it SHALL NOT consult `/proc`, the
runtime's per-pid session records, or any other state that a reboot destroys.

#### Scenario: The record is readable after every process is gone

- **WHEN** the record holds entries for a project and none of the recorded pids or session records exist any more
- **THEN** reading the project's record returns every entry it held, unchanged

#### Scenario: A project never seen has an empty record, not an error

- **WHEN** a project has no record file
- **THEN** reading it returns an empty list of entries and reports that no record exists, rather than raising

### Requirement: Each entry states whether it is resumable right now

Reading the record SHALL report, per entry, whether a transcript for that session exists at
the time of the read, and SHALL report an entry whose transcript is gone as **present and
not resumable** rather than omitting it.

An entry MUST NOT be dropped for being unresumable: a shortened list reads as a complete
one, and the user would be told a smaller fleet existed than did.

#### Scenario: A resumable entry is reported as resumable

- **WHEN** an entry's session has a transcript on disk
- **THEN** the entry is reported with `resumable` true

#### Scenario: An entry whose transcript is gone is kept and marked

- **WHEN** an entry's session has no transcript on disk
- **THEN** the entry is still returned, reported with `resumable` false and a reason naming the missing transcript

### Requirement: The record carries identity only

The record SHALL contain only session id, label, cwd, project, kind and timestamps. It MUST
NOT contain transcript content, message text, tool output, or any value derived from a
project's domain.

#### Scenario: No content is written

- **WHEN** an entry is written for a session whose transcript contains message text
- **THEN** the stored entry contains none of that text, and its fields are limited to identity and timestamps

### Requirement: Recording never breaks discovery

A failure to write the record — unwritable store, malformed existing file, full disk —
SHALL be logged at WARNING and SHALL NOT change what discovery returns or cause it to fail.

#### Scenario: An unwritable store leaves discovery intact

- **WHEN** the record cannot be written
- **THEN** discovery returns its normal answer, and a warning naming the failure is logged

#### Scenario: A corrupt record file is not fatal

- **WHEN** the existing record file cannot be parsed
- **THEN** reading it reports that the record is unreadable, and writing replaces it rather than raising

### Requirement: An entry can be forgotten, and stale entries are bounded

The framework SHALL support removing a named entry from a project's record, and SHALL bound
how long an entry unseen since its last-seen time is retained. Pruning SHALL be reported
rather than silent.

#### Scenario: A named entry is removed

- **WHEN** removal is requested for session id `S` on a project
- **THEN** `S` is absent from the record afterwards and the remaining entries are unchanged

#### Scenario: An entry unseen beyond the retention bound is pruned

- **WHEN** the record is written and an entry's last-seen time is older than the retention bound
- **THEN** that entry is removed and the removal is logged with the session id and its age
