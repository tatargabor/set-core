## IN SCOPE

- How a project names who carries its questions, and how the framework reaches that outbound
  without holding a reference to any particular one.
- The two carriers of an answer — a durable file that waits, and a message that may arrive
  sooner — and which of them is the record.
- Reading an answer back: recognising it, ignoring what is not ours, quarantining what is
  broken, scoping it to the run that asked, and releasing the held groups.

## OUT OF SCOPE

- Any outbound implementation, including any chat or notification client. The framework
  ships none, and the existing one-way notification module is not extended.
- What the outbound does with the question once it has it: rendering, masking, buttons,
  reminders, escalation.
- Guarantees about when a recipient reads. Delivery timing belongs to the recipient's own
  session configuration, not to this contract.

## ADDED Requirements

### Requirement: The outbound is declared by the project and never imported

The framework SHALL resolve who carries a project's questions from that project's own
configuration. The framework SHALL NOT contain a reference to any specific outbound.

#### Scenario: A project declares an outbound

- **WHEN** a project's configuration names a command that carries questions
- **THEN** the framework hands questions to that command
- **AND** the framework's own code names no outbound

#### Scenario: A project declares none

- **WHEN** a project's configuration names no outbound
- **THEN** questions are still registered in the task file and groups are still held
- **AND** the cycle reports that no outbound is declared, rather than failing

### Requirement: The hand-off is best-effort and cannot fail the cycle

A failure to hand a question to an outbound SHALL be reported and SHALL NOT change the
outcome of the section, the group, or the run.

#### Scenario: The outbound is missing, times out, or exits non-zero

- **WHEN** the hand-off fails for any reason
- **THEN** the failure is reported with its error class
- **AND** the run's verdict is what the work produced, unchanged by the hand-off

### Requirement: A file is the record and a message is only sooner

The durable carrier of an answer SHALL be a file at the location the envelope stated. A
message on an agent bus MAY also carry the answer and MAY arrive first; it SHALL NOT be the
only carrier, and no requirement here depends on a recipient reading within any period.

#### Scenario: Nothing is running when the answer is given

- **WHEN** the answer is produced while no session of the asking project is running
- **THEN** the answer is on disk when a session next runs
- **AND** it is applied then

#### Scenario: Both carriers deliver

- **WHEN** an answer arrives both as a message and as a file
- **THEN** the task is answered once
- **AND** the second arrival is recognised as already applied rather than applied again

### Requirement: A question is handed over once, however often the cycle runs

A question that has already been handed to an outbound SHALL NOT be handed over again while
it is still awaiting an answer. Re-running the cycle, restarting it, or resuming it SHALL NOT
produce a second copy of the same question.

#### Scenario: The nightly cycle restarts while a question is outstanding

- **WHEN** a cycle runs again and the same task is still awaiting an answer
- **THEN** the question is not handed to the outbound a second time
- **AND** the run reports it as already outstanding rather than as newly raised

#### Scenario: A question is deliberately re-raised

- **WHEN** an outstanding question is explicitly reissued, for example because it went
  unanswered for too long
- **THEN** the reissue is recorded as such against the same identity
- **AND** it does not become a second, independently answerable question

### Requirement: A bus notification addresses an identity that outlives a session

Where an agent bus is used to notify an outbound, the notification SHALL address the
recipient by an identity that survives the end of a session. It SHALL NOT be addressed to a
single session's identity.

#### Scenario: The recipient's session ends before it reads

- **WHEN** a notification is addressed to the recipient's durable identity and every session
  of that recipient has since ended
- **THEN** a later session of the same recipient is still addressed by that entry

#### Scenario: A session identity is used by mistake

- **WHEN** a notification is addressed to one session's identity and that session never
  returns
- **THEN** the entry is undeliverable for the lifetime of the room
- **AND** the contract forbids this form of addressing for questions and answers

### Requirement: The key is a field, and unrecognised entries are left untouched

An answer SHALL be identified by a key carried inside it, not by its filename. A reader that
does not recognise a key SHALL leave that answer exactly as it found it.

#### Scenario: Two readers share one answer directory

- **WHEN** the directory holds answers whose keys belong to another reader
- **THEN** this reader applies only the ones it recognises
- **AND** the others are neither moved, altered, nor deleted

#### Scenario: The filename disagrees with the key

- **WHEN** an answer's filename suggests one task and its key names another
- **THEN** the key decides
- **AND** the filename is not used to route the answer

### Requirement: A malformed answer is quarantined with a reason and never deleted

An answer that cannot be parsed, that carries no key, that carries no answer text, or whose
task cannot be found SHALL be moved aside with a stated reason. It SHALL NOT be deleted, and
it SHALL NOT be applied to any other task.

#### Scenario: The answer names a task that no longer exists

- **WHEN** an answer's key names a task that is absent or no longer awaiting
- **THEN** the answer is quarantined with that reason
- **AND** no neighbouring task is answered in its place

#### Scenario: The answer is not readable

- **WHEN** an answer cannot be parsed
- **THEN** it is quarantined with the parse error's class
- **AND** the original content is preserved

### Requirement: An answer is applied to the run that asked

Applying an answer SHALL honour the same run scoping the engine already uses for its locks.
An answer SHALL NOT release work belonging to a different run.

#### Scenario: Two runs of the same project are in flight

- **WHEN** an answer arrives for a question raised by one of them
- **THEN** only that run's held groups are released
- **AND** the other run is unaffected

### Requirement: Applying an answer releases the work it was holding

When an answer is applied, the awaiting task SHALL be recorded as answered and the groups
that depended on it SHALL become runnable, using the engine's existing route for carrying an
answer into the next run.

#### Scenario: The held group runs

- **WHEN** the last awaiting task of a group is answered
- **THEN** that group is no longer holding its dependants
- **AND** the answer is available to the next run as context, through the route that already
  exists rather than a second one

#### Scenario: One of several questions is answered

- **WHEN** a group holds more than one awaiting task and one is answered
- **THEN** that task is recorded as answered
- **AND** the group continues to hold its dependants until the rest are answered
