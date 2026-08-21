## IN SCOPE

- How a project names who carries its questions, and how the framework reaches that outbound
  without holding a reference to any particular one.
- The operator opt-in a network-reaching declared command requires, and why the framework
  cannot check it for itself.
- The hand-off: best-effort, never fatal to the cycle, retried after failure, and not
  repeated while a question is already outstanding.

## OUT OF SCOPE

- Any outbound implementation. What an outbound does with a question — rendering, masking,
  buttons, reminders, escalation — is its own, and is measurable only there.
- Reading an answer back. That is `deferred-work-connector` (in `work-cycle-engine-apply-first`), which documents behaviour
  already shipped in `lib/set_workcycle/connector.py`.
- Guarantees about when a recipient reads. Delivery timing belongs to the recipient's own
  session configuration, not to this contract.

## ADDED Requirements

### Requirement: The outbound is declared by the project and never imported

The framework SHALL resolve who carries a project's questions from that project's own
configuration. The framework SHALL NOT contain a reference to any specific outbound.

#### Scenario: A project declares an outbound

- **WHEN** a project's configuration names a command that carries questions
- **THEN** the framework hands questions to that command
- **AND** no name of any outbound appears in the framework's own source

#### Scenario: A project declares none

- **WHEN** a project's configuration names no outbound
- **THEN** questions are still marked awaiting and still hold the groups that depend on them
- **AND** the cycle reports that no outbound is declared, which is not the same as reporting
  that there is no question

### Requirement: A declared command that reaches a network requires an explicit operator opt-in

A question outbound reaches something outside this machine. The framework SHALL NOT run a
declared outbound on the strength of the project's declaration alone: an operator-held
setting, outside the project's own tree, SHALL be required before any outbound runs.

#### Scenario: The project declares an outbound and the operator has not opted in

- **WHEN** a project's configuration names an outbound and no operator opt-in is present
- **THEN** no outbound is run
- **AND** the cycle reports that an outbound is declared but not enabled, naming where the
  opt-in belongs

#### Scenario: A work unit edits its own tree's configuration

- **WHEN** a unit changes the declared outbound in the tree it is running in
- **THEN** the changed declaration cannot by itself cause a command to be run on the next
  cycle
- **AND** the opt-in, which lives outside that tree, still governs

### Requirement: The hand-off is best-effort and cannot fail the cycle

A failure to hand a question to an outbound SHALL be reported and SHALL NOT change the
outcome of the section, the group, or the run.

#### Scenario: The outbound is missing, times out, or exits non-zero

- **WHEN** the hand-off fails for any reason
- **THEN** the failure is reported with its error class
- **AND** the run's verdict is what the work produced, unchanged by the hand-off

### Requirement: A failed hand-off is retried, and an unheard question is reported as unheard

A question whose hand-off has never succeeded SHALL be attempted again on a later cycle. The
system SHALL distinguish *outstanding with somebody* from *never successfully handed over*,
and SHALL report the second as an unheard question rather than as a question in flight.

#### Scenario: The outbound is unreachable overnight

- **WHEN** every hand-off attempt for a question has failed
- **THEN** later cycles attempt it again
- **AND** the question is reported as never handed over, not as awaiting a person

#### Scenario: The hand-off eventually succeeds

- **WHEN** a retried hand-off succeeds
- **THEN** the question is recorded as handed over
- **AND** it is not handed over again while it remains outstanding

### Requirement: A question that is already outstanding is not handed over again

A question recorded as successfully handed over SHALL NOT be handed over again while it is
still awaiting an answer. Re-running, restarting or resuming the cycle SHALL NOT produce a
second copy of the same question.

#### Scenario: The nightly cycle restarts while a question is outstanding

- **WHEN** a cycle runs again and the same task is still awaiting an answer that was handed
  over successfully
- **THEN** the question is not handed to the outbound a second time
- **AND** the run reports it as outstanding rather than as newly raised

#### Scenario: A question is deliberately reissued

- **WHEN** an outstanding question is explicitly reissued
- **THEN** the reissue is recorded against the same identity
- **AND** it does not become a second, independently answerable question

### Requirement: A bus notification addresses an identity that outlives a session

Where an agent bus is used to notify an outbound, the notification SHALL address the recipient
by an identity that survives the end of a session, and SHALL NOT be addressed to a single
session's identity. No behaviour SHALL depend on the notification being read.

#### Scenario: A session identity is used

- **WHEN** a notification is addressed to one session's identity and that session never
  returns
- **THEN** the entry is undeliverable for the lifetime of the room

#### Scenario: The bus is never read

- **WHEN** no session of the recipient ever reads the notification
- **THEN** the question is still recorded as handed over or not handed over by the outcome of
  the hand-off itself
- **AND** nothing about the cycle's behaviour depends on the notification
