## IN SCOPE
- Where a recorded agent's session identity comes from, and in what order.
- What the framework's own start intent may and may not override.
- The tri-state of the framework's answer: unreachable, reachable-and-empty, populated.
- What a reason line may claim when no source knows a session.

## OUT OF SCOPE
- How long an entry lives, and which write may retire one — see `roster-entry-lifetime`.
- Reading live process state at read time. The roster answers after a reboot.
- Refusing or permitting a restore. That is the restore path's decision.
- The race in which two processes claim one session; the owner's guard covers it and was
  measured working.

## ADDED Requirements

### Requirement: A recorded agent's session identity is taken from the runtime first and the framework second

The roster SHALL record a session identity for an agent whenever any source knows one, and
SHALL consult those sources in a fixed order: the runtime's per-pid record first, and the
session the framework itself started that agent on second.

The framework's answer SHALL fill a silence and SHALL NOT override a statement. The two answer
different questions — what the process is bound to now, versus what it was asked to resume —
and they can disagree, which is precisely the case that produced this defect. Where they
disagree the process's own answer is the one the reader is asking about.

Measured before this change: an agent the framework started with `--resume <S>`, whose runtime
record never appeared, was recorded with no session id at all, while the owner was reporting
`resumed_session: <S>` for that same pid.

#### Scenario: The runtime's answer is used when it exists
- **GIVEN** an agent whose runtime record names a session
- **AND** the framework recorded a different session for that pid
- **WHEN** the roster records it
- **THEN** the entry carries the session from the runtime's record

#### Scenario: The framework's answer fills a silence
- **GIVEN** an agent with no runtime record
- **AND** the framework started it on a known session
- **WHEN** the roster records it
- **THEN** the entry carries that session
- **AND** the entry is not keyed as having no session

#### Scenario: Neither source knows
- **GIVEN** an agent with no runtime record that the framework did not start
- **WHEN** the roster records it
- **THEN** the entry is recorded with no session id

### Requirement: The framework's session knowledge travels as a pid-keyed mapping supplied by the caller

The recording call SHALL accept the framework's session knowledge as a mapping from pid to
session id, supplied by its caller, in the same shape and from the same answer the label
mapping already travels in.

The roster SHALL NOT ask the owner itself. It is a document, and a document that opened a
socket to a service would make every write depend on that service being up.

#### Scenario: The caller supplies it from the answer it already has
- **WHEN** the fleet listing records the roster
- **THEN** it passes the session knowledge taken from the same owner answer it used for labels
- **AND** no additional request is made to the owner

#### Scenario: The roster opens no socket
- **WHEN** the roster module is inspected for a client of the agent owner
- **THEN** none is found

### Requirement: An unreachable source is distinct from a source that knows nothing

The mapping SHALL distinguish three states: **absent** — the framework could not be asked;
**empty** — it was asked and holds nothing; and **populated**. These SHALL NOT be collapsed.

An unreachable owner and an owner holding no agents lead to different claims: the first is a
gap in what is known, the second is a statement about the fleet. The listing path already
draws this distinction for the label mapping and states why; recording SHALL preserve it
rather than flatten it on the way through.

#### Scenario: Absent is not empty
- **GIVEN** the framework could not be asked
- **WHEN** an agent with no runtime record is recorded
- **THEN** it is recorded with no session id
- **AND** nothing is inferred from the absence of an answer

#### Scenario: Empty behaves as it did before
- **GIVEN** the framework was asked and holds nothing
- **WHEN** an agent with no runtime record is recorded
- **THEN** the entry is the same as one recorded with no mapping supplied at all

### Requirement: A reason line states what was actually asked

Where an entry cannot be resumed because no source knows a session, the reason SHALL say that
no source knows one, and SHALL NOT claim that no session was ever recorded for that agent.

The distinction is the difference between a fact and a false one: for an agent the framework
started, a session *was* recorded — by the framework, at the moment of starting — and the
previous wording denied a fact the system was simultaneously reporting elsewhere.

#### Scenario: A framework-started agent no longer carries the false reason
- **GIVEN** an agent the framework started on a known session
- **WHEN** the roster is read
- **THEN** its entry does not state that no session id was ever recorded for it

#### Scenario: A genuinely unknown agent says so accurately
- **GIVEN** an agent no source knows a session for
- **WHEN** the roster is read
- **THEN** the reason states that no source knows one

### Requirement: The key builder's documentation matches its behaviour, and the behaviour is held in a test

The key used for an agent with no session identity SHALL be documented accurately, and its
actual properties SHALL be asserted in a test rather than described in prose.

Measured: its documentation claimed the key is "stable across sightings" and derived "never
from its pid", and both are false — with no name it falls back to the pid, and the key changes
the moment the runtime supplies a name, so one agent could leave more than one entry behind.
Prose describing behaviour is the carrier that decays without anything noticing.

#### Scenario: The pid fallback is asserted
- **GIVEN** an agent with no name
- **WHEN** its no-session key is built
- **THEN** the key contains its pid

#### Scenario: The key's instability across a naming event is asserted
- **GIVEN** the same agent seen once without a name and once with one
- **WHEN** its no-session key is built each time
- **THEN** the two keys differ
