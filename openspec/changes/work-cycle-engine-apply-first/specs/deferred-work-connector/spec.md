## IN SCOPE
- Setting a work unit aside with a resume condition that is named rather than implied
- Turning an open decision into a durable stop marker in the change's task file
- A filesystem connector through which answers arrive, keyed on change and task
- Surviving partial writes, duplicate answers for one key, and several uploaders
- Making consumption of an answer visible rather than inferring it from directory state

## OUT OF SCOPE
- Any particular uploader — a chat bridge, the framework's surface, or a person filling the
  directory by hand is the caller's business
- Notifying a human that a question exists (delivery is the caller's concern)
- Resuming automatically once a condition clears — the caller decides when to run again

## ADDED Requirements

### Requirement: A set-aside unit names its resume condition
The engine SHALL allow a work unit to be set aside with a stated condition for resuming it, and SHALL
record that condition in machine-readable form. The condition SHALL NOT be limited to a human answer:
the availability of an external system SHALL be expressible by the same mechanism.

#### Scenario: Awaiting a human answer
- **WHEN** a unit is set aside because a decision needs a person
- **THEN** the recorded condition identifies the decision awaiting an answer

#### Scenario: Awaiting an external system
- **WHEN** a unit is set aside because a system it depends on is unavailable
- **THEN** the recorded condition names that dependency
- **AND** the engine does NOT describe the unit as waiting for a human

#### Scenario: A unit cannot be set aside without a condition
- **WHEN** a unit is set aside with no condition given
- **THEN** the engine refuses, because a condition that is not named cannot be observed

### Requirement: An open decision becomes a durable stop marker
When a work unit returns open decisions, the engine SHALL mark the corresponding tasks in the
change's task file as awaiting a human, so that the stop survives the run that produced it and is
visible to any later reader of the file.

#### Scenario: Open decision is written into the task file
- **WHEN** a unit returns an open decision naming a task
- **THEN** that task is marked in the file as awaiting a human answer
- **AND** the question text is recorded with it

#### Scenario: The marker outlives the run
- **WHEN** the engine is restarted after a unit returned an open decision
- **THEN** the marked task is still reported as awaiting an answer

### Requirement: Answers arrive through a keyed directory
The engine SHALL read answers from a directory, keying each answer to the change and task it
answers. The key SHALL be carried inside the answer document; a file's name SHALL NOT be the only
carrier of its identity.

#### Scenario: An answer releases its task
- **WHEN** an answer document naming a change and an awaiting task is placed in the directory
- **THEN** the engine records the answer against that task and the task is no longer awaiting

#### Scenario: An answer for an unknown task
- **WHEN** an answer names a task that is not awaiting an answer
- **THEN** the engine reports it as unmatched and leaves it in place rather than discarding it

### Requirement: The connector tolerates a partially written answer
The engine SHALL treat a malformed answer document as a possible in-flight write. It SHALL defer
such a document and retry it on a later intake, and SHALL only quarantine it after a bounded number
of failed attempts.

#### Scenario: Half-written file is retried, not quarantined
- **WHEN** an answer document cannot be parsed on its first intake
- **THEN** it is deferred and remains eligible for a later intake
- **AND** it is NOT quarantined on that first failure

#### Scenario: Persistently malformed file is quarantined with its reason
- **WHEN** a document has failed to parse on the configured number of successive intakes
- **THEN** it is quarantined and the reason is recorded alongside it

#### Scenario: A deferred file that later parses is consumed normally
- **WHEN** a document that was deferred parses successfully on a later intake
- **THEN** it is consumed as any other answer

### Requirement: Several answers may exist for one key
The engine SHALL accept more than one answer document for the same key, SHALL apply the most recent
one, and SHALL retain the others rather than deleting them. Answer documents SHALL be named so that
two independent uploaders cannot silently overwrite one another.

#### Scenario: Two uploaders answer the same question
- **WHEN** two answer documents for the same key are present
- **THEN** the most recent is applied
- **AND** the other is retained

#### Scenario: Names do not collide
- **WHEN** an answer document is written by an uploader
- **THEN** its name carries the uploader's identity and a timestamp
- **AND** a second uploader writing for the same key produces a different name

### Requirement: Answer intake runs at the entry point on every path
The engine SHALL take in pending answers at its entry point, on every path that starts work, and
SHALL NOT make intake a side effect of any one command variant.

#### Scenario: Intake happens on a single-unit run
- **WHEN** the engine is asked to run one work unit
- **THEN** pending answers are taken in before the unit is selected

#### Scenario: Intake happens on a status query
- **WHEN** the engine is asked what is runnable
- **THEN** pending answers are taken in before the answer is computed
- **AND** a task released by a pending answer is reported as runnable

### Requirement: Consumption is recorded, not inferred
The engine SHALL record when an answer was consumed, on the answer itself or in its own log. The
state of the answer directory SHALL NOT be the only evidence that intake happened.

#### Scenario: A consumed answer is stamped
- **WHEN** an answer is applied to a task
- **THEN** the time of consumption is recorded

#### Scenario: An unconsumed answer is distinguishable
- **WHEN** answers are present in the directory
- **THEN** those already consumed are distinguishable from those not yet consumed
- **AND** neither state is concluded from the number of files present
