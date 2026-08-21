## IN SCOPE

- The envelope a work cycle produces when a section needs a person.
- The rules that make it safe to produce: a declared version, a required audience the
  framework never supplies, structured options, a stated answer location that is not a local
  path, and what the framework may keep of the question's content.

## OUT OF SCOPE

- The envelope an answer comes back in, and everything about reading it — that is
  `deferred-work-connector` (in `work-cycle-engine-apply-first`), documenting behaviour already shipped in
  `lib/set_workcycle/connector.py`.
- What an outbound does once it has the envelope, including masking, redaction and audience
  filtering. Those are measurable only where the text becomes a message.
- The vocabulary of audiences, the exact field spelling, and the composition of the key —
  being settled with an existing implementation; named as open questions in `design.md`.

## ADDED Requirements

### Requirement: The awaiting task is the register, and the envelope is derived from it

A question SHALL exist as an awaiting task in the project's own task file before any envelope
is produced. The envelope SHALL be derived from that task and SHALL NOT be the only record of
the question.

#### Scenario: A unit reports an open decision

- **WHEN** a work unit reports an open decision that stops it
- **THEN** the task is marked awaiting in the change's task file with its question
- **AND** any group that declares a dependency on that group is held
- **AND** the envelope produced afterwards carries the identity of that task

#### Scenario: Nothing carried the question anywhere

- **WHEN** no outbound is declared, or the hand-off fails
- **THEN** the question still stands in the task file, and the groups that depend on it are
  still held
- **AND** the cycle reports that nobody was told, rather than reporting that there is no
  question

### Requirement: The envelope declares its version and an unknown version is refused

The envelope SHALL carry a contract version, and a producer SHALL always emit one. A reader
encountering a version it does not understand SHALL refuse the envelope with a stated reason
rather than parse it on a guess.

#### Scenario: A produced envelope carries a version

- **WHEN** the framework produces an envelope
- **THEN** it carries a contract version

#### Scenario: An envelope announces a version the reader does not know

- **WHEN** an envelope declares a version outside the set the reader supports
- **THEN** the reader refuses it, states the version it received, and acts on no other field

### Requirement: The audience is required, and the framework never supplies one

Every question envelope SHALL carry an audience. The framework SHALL NOT supply, infer or
default that value. A project MAY declare its own fail-closed default. An envelope with no
audience SHALL NOT be handed to an outbound.

#### Scenario: A project declares a conservative default

- **WHEN** a project declares that questions raised by a given part of its work belong to a
  given audience
- **THEN** envelopes from that part carry that audience unaltered by the framework

#### Scenario: No audience can be determined

- **WHEN** no audience is declared for a question
- **THEN** the framework produces no envelope for it and says why
- **AND** the question remains awaiting, unanswered rather than misdirected

### Requirement: Options are structured, and a display form is never read back

When a question offers a closed set of choices, the envelope SHALL carry them as a list of
discrete values. A joined, human-readable rendering MAY accompany it for display and SHALL
NOT be parsed back into choices.

#### Scenario: An option contains the separator used for display

- **WHEN** one of the offered choices contains the character used to join them for display
- **THEN** the structured list still carries that choice as one value
- **AND** no reader reconstructs the choices from the joined string

#### Scenario: The question offers no closed set

- **WHEN** a question accepts free text
- **THEN** the envelope carries an empty option list rather than an invented one

### Requirement: The envelope states where the answer belongs, without publishing a local path

The envelope SHALL identify where the answer is to be delivered in a form the framework can
resolve back to a location, and SHALL NOT carry an absolute filesystem path or any other
description of this machine's layout. A reader SHALL NOT infer the location from the identity
of the project or of the outbound.

#### Scenario: The envelope leaves the machine

- **WHEN** an envelope is handed to an outbound that posts it where people can read it
- **THEN** it contains no absolute path, no account name and no local directory name

#### Scenario: A second outbound answers a question it did not design for

- **WHEN** an outbound that has never served this project receives an envelope
- **THEN** what the envelope states is sufficient to deliver an answer
- **AND** it needs no knowledge of the project's layout or of any other outbound

### Requirement: The framework keeps the question content only where the register is

The framework SHALL write the question's text into the project's own task file, which is the
register. It SHALL NOT write the question text into set-core's own repository, into a cache,
or into any log line.

*The matching rule for the ANSWER document's free-text fields lives in
`work-cycle-answer-is-data`, so that one enumeration has one owner. An earlier draft stated it
in both places, which is two registers for one obligation.*

#### Scenario: A question is routed and something goes wrong

- **WHEN** an envelope is refused, mis-shaped, or fails to reach an outbound
- **THEN** the diagnostic names the field, the count and the error class, and contains no
  question text
