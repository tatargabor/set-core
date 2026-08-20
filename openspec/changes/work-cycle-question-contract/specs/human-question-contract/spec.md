## IN SCOPE

- The envelope a work cycle produces when a section needs a person, and the envelope an
  answer comes back in.
- The rules that make the envelope safe to read: a declared version, a required audience the
  framework never supplies, structured options, and a stated place for the answer.
- What the framework may keep of a question: nothing derived from its content.

## OUT OF SCOPE

- Who carries the question to a human, and how it reaches them — `question-outbound-binding`.
- Masking, redaction or audience filtering of the question text. That is measurable only
  where the text becomes a message, and belongs to whoever carries it out.
- Any surface that displays pending questions.
- The vocabulary of audiences, the exact field spelling, and the composition of the key.
  These are being settled with an existing implementation and are named as open questions in
  `design.md`; this spec fixes the obligations, not the wire spelling.

## ADDED Requirements

### Requirement: The task file is the register, and the envelope is derived from it

A question SHALL exist as a task in the project's own task file before any envelope is
produced. The envelope SHALL be derived from that task and MUST NOT be the only record of
the question.

#### Scenario: A section reports that it needs a person

- **WHEN** a work-cycle section returns `NEEDS_INPUT`
- **THEN** the question is written into the change's task file as an awaiting task
- **AND** the groups that depend on it remain held
- **AND** the envelope produced afterwards carries the identity of that task

#### Scenario: Nothing carried the question anywhere

- **WHEN** no outbound is declared, or the hand-off fails
- **THEN** the question still stands in the task file and the groups are still held
- **AND** the cycle reports that nobody was told, rather than reporting that there is no
  question

### Requirement: The envelope declares its version and an unknown version is refused

The envelope SHALL carry a contract version. A reader encountering a version it does not
understand SHALL refuse the envelope with a stated reason rather than parse it on a guess.

#### Scenario: An envelope announces a version the reader does not know

- **WHEN** an envelope declares a version outside the set the reader supports
- **THEN** the reader refuses it and states the version it received
- **AND** no field of that envelope is read

### Requirement: The audience is required, and the framework never supplies one

Every question envelope SHALL carry an audience. The framework SHALL NOT supply, infer or
default that value. A project MAY declare its own fail-closed default. An envelope with no
audience SHALL be refused by whoever would carry it.

#### Scenario: A project declares a conservative default

- **WHEN** a project states that questions of a given origin belong to a given audience
- **THEN** envelopes from that origin carry that audience
- **AND** the framework does not alter it

#### Scenario: An envelope arrives with no audience

- **WHEN** an envelope carries no audience, or an empty one
- **THEN** the outbound refuses to carry it and states why
- **AND** the question remains in the task file, unanswered rather than misdirected

### Requirement: Options are structured, and a display form is never read back

When a question offers a closed set of choices, the envelope SHALL carry them as a list of
discrete values. A joined, human-readable rendering MAY accompany it for display and SHALL
NOT be parsed back into choices.

#### Scenario: An option contains the separator used for display

- **WHEN** one of the offered choices contains the character used to join them for display
- **THEN** the structured list still carries that choice as one value
- **AND** no reader reconstructs the choices from the joined string

#### Scenario: The question accepts free text

- **WHEN** a question offers no closed set of choices
- **THEN** the envelope carries an empty option list rather than an invented one

### Requirement: The envelope states where the answer is expected

The envelope SHALL carry the location the answer is to be written to. A reader SHALL NOT
infer that location from the identity of the project or of the outbound.

#### Scenario: A second outbound answers a question it did not design for

- **WHEN** an outbound that has never served this project receives a question
- **THEN** it writes the answer to the location the envelope states
- **AND** it needs no knowledge of the project's layout or of any other outbound

#### Scenario: The stated location cannot be written to

- **WHEN** the outbound cannot write to the location the envelope states
- **THEN** it records the answer somewhere it can write and says that it did so
- **AND** the answer is not discarded

### Requirement: The framework persists nothing derived from the question content

The framework SHALL NOT write the question text, the answer text, or any value derived from
them into its own repository, into a cache, or into any log line. Diagnostics SHALL record
shape, counts and error classes only.

#### Scenario: A question is routed and something goes wrong

- **WHEN** an envelope is refused, mis-shaped, or fails to reach an outbound
- **THEN** the diagnostic names the field, the count and the error class
- **AND** it contains no part of the question or answer text
