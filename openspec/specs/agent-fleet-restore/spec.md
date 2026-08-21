# agent-fleet-restore Specification

## Purpose
TBD - created by archiving change fleet-agent-restore. Update Purpose after archive.

## Requirements

### Requirement: Restore is a per-project act over the whole recorded list

The framework SHALL expose a restore act taking one project and no per-entry selection, and
SHALL attempt every entry in that project's record. Restore MUST NOT be triggered
automatically by discovery, by a page load, or by the framework starting.

#### Scenario: Restoring a project attempts every recorded entry

- **WHEN** restore is requested for a project whose record holds `N` entries
- **THEN** the result carries exactly `N` per-entry outcomes, one per recorded entry

#### Scenario: Restoring a project with an empty record changes nothing

- **WHEN** restore is requested for a project whose record is empty
- **THEN** no agent is started and the result reports zero entries attempted

### Requirement: Each entry is restored by starting an agent that resumes its session

For an entry that is resumable and not already live, the framework SHALL start an agent in
the entry's `cwd` through the service that owns agent lifetimes, resuming the entry's
session id. The framework itself MUST NOT fork the agent process, and the restore logic
MUST NOT be placed in that owner service.

#### Scenario: A resumable entry comes back as a resumed session

- **WHEN** an entry is resumable, its session is not live, and restore runs
- **THEN** an agent is started in the entry's `cwd` resuming that session id, and the entry's outcome is `started` carrying the new label

#### Scenario: The owner service being unavailable is reported, not swallowed

- **WHEN** restore runs and the service that owns agent lifetimes cannot be reached
- **THEN** the request fails with an explicit unavailable answer, and no entry is reported as started

### Requirement: A live session is skipped, never resumed

The framework SHALL NOT resume a session that a live process is bound to, because a resume
against a live session forks its conversation silently. Such an entry SHALL be reported as
skipped with that reason, and the running agent SHALL be left untouched.

#### Scenario: An already-running session is skipped

- **WHEN** an entry's session is bound to a live process and restore runs
- **THEN** that entry's outcome is `skipped` with a reason naming the live session, no resume is attempted, and the running agent is not stopped

#### Scenario: An indeterminate liveness is treated as live

- **WHEN** it cannot be determined whether an entry's session is bound to a live process
- **THEN** the entry is skipped rather than resumed, and the reason states that liveness was indeterminate

### Requirement: An unresumable entry is skipped with its reason

An entry with no transcript SHALL be reported as skipped with a reason naming the missing
transcript. It MUST NOT be reported as failed, and it MUST NOT be silently omitted from the
result.

#### Scenario: An entry with no transcript is skipped and named

- **WHEN** an entry has no transcript and restore runs
- **THEN** its outcome is `skipped` with a reason naming the missing transcript, and it appears in the result

### Requirement: The result reports every entry separately, and a partial restore reads as partial

The restore result SHALL carry one outcome per entry with its reason, and SHALL carry
counts of started, skipped and failed. A restore in which any entry did not start MUST NOT
be presented as a completed restore.

#### Scenario: A mixed restore reports its parts

- **WHEN** restore runs over 9 entries of which 3 start, 4 are skipped and 2 fail
- **THEN** the result reports 3 started, 4 skipped, 2 failed, with a reason on each of the 6 that did not start

#### Scenario: One entry failing does not abandon the rest

- **WHEN** an entry fails to start
- **THEN** the remaining entries are still attempted, and the failure is reported against that entry alone

### Requirement: The surface offers restore per project and shows what happened

The fleet screen SHALL offer restore for a project whose record is non-empty, SHALL state
how many entries the record holds before the act is taken, and SHALL show the per-entry
outcome afterwards, including the reason for every entry that did not start.

A project whose record is empty SHALL NOT present a restore control that would do nothing.

#### Scenario: A project with a record offers restore and names the count

- **WHEN** a project's record holds entries and its screen is opened
- **THEN** a restore control is offered stating how many entries would be attempted

#### Scenario: The outcome of every entry is visible after restoring

- **WHEN** restore completes with entries that were skipped or failed
- **THEN** the screen shows each of those entries with its reason, rather than a single success or failure message

#### Scenario: An empty record offers no restore control

- **WHEN** a project has no recorded entries
- **THEN** no restore control is offered for it
