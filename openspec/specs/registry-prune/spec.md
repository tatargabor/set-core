# registry-prune Specification

## Purpose
TBD - created by archiving change registry-prune. Update Purpose after archive.
## Requirements
### Requirement: The prune never removes anything from disk
The prune SHALL NOT delete, move, or truncate any file, directory, git worktree directory, or
git branch, under any flag or combination of flags. Its only permitted mutations are the
registry file and — via `git worktree prune` — git's administrative records for worktrees
whose directory is already absent.

#### Scenario: A full prune leaves the tree byte-identical
- **WHEN** a prune runs to completion over a fixture containing registered projects, live
  worktrees, and orphaned worktree records
- **THEN** a recursive content hash of the tree SHALL be unchanged except for the registry
  file and `.git/worktrees/` administrative records

#### Scenario: A branch behind an orphaned worktree survives
- **WHEN** an orphaned worktree record for branch `change/x` is pruned
- **THEN** `change/x` SHALL still exist and SHALL point at the same commit

### Requirement: Deregistration requires the directory to be absent
An entry SHALL be deregistered if and only if its `path` is not an existing directory. No
other property — age, emptiness, missing orchestration state, name — SHALL cause
deregistration.

#### Scenario: A live directory is never deregistered
- **WHEN** a registered entry's path is an existing directory, however old or empty
- **THEN** the entry SHALL remain in the registry

#### Scenario: A deleted directory is deregistered
- **WHEN** a registered entry's path does not exist and its parent directory does
- **THEN** the entry SHALL be removed from the registry

### Requirement: An unreachable path is reported, not deregistered
When an entry's path does not exist AND its parent directory also does not exist, the prune
SHALL treat the state as unknown: the entry SHALL be kept and reported separately from the
deregistered ones.

#### Scenario: An unmounted filesystem
- **WHEN** an entry points at `/mnt/nas/proj` and `/mnt/nas` does not exist
- **THEN** the entry SHALL be kept and reported as unreachable rather than deregistered

### Requirement: Only git-flagged prunable worktree records are pruned
For each registered project whose directory exists, the prune SHALL read
`git worktree list --porcelain` and act only on records git itself flags `prunable`. A
repository with no prunable records SHALL be skipped without mutating it. The prune SHALL NOT
pass an expiry option.

#### Scenario: A live worktree is untouched
- **WHEN** a project has a worktree whose directory exists
- **THEN** that worktree record SHALL remain and its directory SHALL be unchanged

#### Scenario: No prunable records
- **WHEN** a project has no prunable worktree records
- **THEN** no git mutation SHALL be attempted on that repository

### Requirement: Archiving marks an entry without removing it
Archiving SHALL set `archived: true` and `archivedAt` on the existing registry entry. The
entry SHALL remain in the registry with all other fields intact, and nothing on disk SHALL be
touched. Clearing the flag SHALL restore the prior state exactly.

#### Scenario: Archive is reversible
- **WHEN** an entry is archived and then un-archived
- **THEN** the entry SHALL be byte-equivalent to its pre-archive state apart from the removed
  `archived` and `archivedAt` fields

#### Scenario: Archiving does not deregister
- **WHEN** an entry is archived
- **THEN** it SHALL still be present in the registry file

### Requirement: Archiving requires both an explicit threshold and the E2E location
An entry SHALL be archived only when the operator supplies an age threshold AND the entry's
path is under the framework's E2E run root. There SHALL be no default threshold: a prune
invoked without one SHALL archive nothing.

#### Scenario: A bare prune archives nothing
- **WHEN** the prune runs without an archive threshold
- **THEN** no entry SHALL gain an `archived` field

#### Scenario: An old project outside the E2E root
- **WHEN** a registered project outside the E2E run root is older than the supplied threshold
- **THEN** it SHALL NOT be archived

#### Scenario: A recent E2E run
- **WHEN** an entry under the E2E run root is newer than the supplied threshold
- **THEN** it SHALL NOT be archived

### Requirement: Archiving refuses to hide a project in a broken or running state
The prune SHALL refuse to archive an entry that has open issues or a live sentinel or
orchestrator process, and SHALL report each refusal with its reason.

#### Scenario: Open issues block archiving
- **WHEN** an otherwise eligible entry has at least one open issue
- **THEN** it SHALL NOT be archived and the refusal SHALL name the open-issue count

#### Scenario: A live process blocks archiving
- **WHEN** an otherwise eligible entry has a live sentinel or orchestrator PID
- **THEN** it SHALL NOT be archived and the refusal SHALL name the running process

### Requirement: Preview mode writes nothing
In preview mode the prune SHALL report every action it would take and SHALL perform no write
at all — including no write to the registry file and no backup.

#### Scenario: A preview leaves the registry untouched
- **WHEN** the prune runs in preview mode over a registry with deregistrable entries
- **THEN** the registry file's content and modification time SHALL be unchanged

### Requirement: The registry is backed up before it is written
Before any mutation of the registry file, the prune SHALL write a timestamped copy alongside
it. Failure to write the backup SHALL abort the prune before any mutation.

#### Scenario: Backup precedes mutation
- **WHEN** a prune deregisters at least one entry
- **THEN** a timestamped backup holding the pre-prune content SHALL exist afterwards

#### Scenario: An unwritable backup aborts
- **WHEN** the backup cannot be written
- **THEN** the registry SHALL be left unchanged and the prune SHALL report the failure

### Requirement: A mutating prune confirms before acting
A prune that would mutate anything SHALL print its plan and require confirmation, unless the
operator passes an explicit assume-yes option or preview mode is active.

#### Scenario: Declining the confirmation
- **WHEN** the operator declines at the prompt
- **THEN** nothing SHALL be written

#### Scenario: Assume-yes skips the prompt
- **WHEN** the operator passes the assume-yes option
- **THEN** the prune SHALL proceed without prompting

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

