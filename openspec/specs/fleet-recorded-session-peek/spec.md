# fleet-recorded-session-peek Specification

## Purpose
TBD - created by archiving change fleet-recorded-session-peek. Update Purpose after archive.

## Requirements

### Requirement: A recorded session can be read without being resumed

The framework SHALL expose a read of the last turns of a recorded entry's session, addressed by
the project and the entry's key, using the transcript that entry would be resumed from. The read
MUST NOT start a process, resume a session, or alter the record in any way.

The number of turns returned SHALL be bounded, and the bound SHALL be applied by reading the END
of the transcript — a session with thousands of turns must cost the same as one with ten.

#### Scenario: The last turns of a recorded session are readable

- **WHEN** a read is requested for a recorded entry whose transcript exists
- **THEN** the last turns of that transcript are returned, and no process is started and no session is resumed

#### Scenario: A long transcript costs no more than a short one

- **WHEN** a read is requested for an entry whose transcript holds far more turns than the bound
- **THEN** only the end of the transcript is read, and the answer states that earlier turns exist rather than implying the session begins there

### Requirement: An unreadable entry says why, and never renders as an empty session

An entry with no session id, with no transcript on disk, or whose transcript cannot be read SHALL
be answered with a stated problem naming which of those it is. An empty answer with no problem
SHALL mean exactly one thing: the transcript was read and holds no conversation.

#### Scenario: A missing transcript is named, not drawn as emptiness

- **WHEN** a read is requested for an entry whose transcript is gone
- **THEN** the answer carries a problem naming the missing transcript, and it is distinguishable from a transcript that was read and was empty

#### Scenario: An entry that was never given a session id is refused with that reason

- **WHEN** a read is requested for an entry that has no session id recorded
- **THEN** the answer states that there is no session to read, rather than reporting an empty conversation

#### Scenario: A key that is not recorded is a not-found, not an empty read

- **WHEN** a read is requested for a key the project's record does not hold
- **THEN** the request fails as not-found, and no answer describing a conversation is returned

### Requirement: Nothing read from a transcript is written down

Content read from a transcript SHALL be returned to the caller and persisted nowhere: not in a
cache, not in a log line, not in an error message, not in browser storage, and not in any
artifact the repository holds. Diagnostics about a failed read SHALL name the file and the kind
of failure, never a line of its content.

This is the confidentiality boundary the framework already draws: a project's data may be READ
and displayed at runtime, and none of it may be persisted.

#### Scenario: A failed read logs the failure without the content

- **WHEN** a transcript cannot be read and the failure is logged
- **THEN** the log line names the file and the failure kind, and carries no line of the transcript

#### Scenario: The answer is not cached

- **WHEN** the same entry is read twice
- **THEN** the transcript is read again both times, and no copy of its content is held between the two reads
