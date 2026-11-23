# fleet-work-agent-done Specification

## Purpose
TBD - created by archiving change fleet-work-agent-done. Update Purpose after archive.

## Requirements

### Requirement: A work agent can end itself with a done step

`set-fleet-mandate done "<line>"` SHALL be accepted only from an agent whose mandate is open, of kind
`work`, and whose requester is recorded. In that order, it SHALL post the line to the requester seat on
the bus, mark the mandate ended with the reason `agent-done`, and stop the agent's own label through the
fleet's stop route. If the post fails, nothing SHALL be ended or stopped, and the failure SHALL be printed.

#### Scenario: The work is over
- **WHEN** an agent-requested `work` agent runs `set-fleet-mandate done "answered the three questions"`
- **THEN** the requester seat receives the line, the mandate is ended with reason `agent-done`, the agent's label is stopped, and the roster still lists the session as resumable

#### Scenario: No mandate, or not a work mandate
- **WHEN** the done step is run by an agent with no mandate, a `desk` mandate, or a mandate without a requester
- **THEN** it is refused with the reason, and nothing is posted, ended or stopped

#### Scenario: The bus cannot be reached
- **WHEN** the post to the requester fails
- **THEN** the mandate stays open, the agent keeps running, and the failure is printed

### Requirement: agent-done is never reported as fulfilled

A mandate ended with `agent-done` SHALL be reported as ended by the agent's own claim. The inventory and
the screen SHALL NOT render it as fulfilled.

#### Scenario: Reading an agent-done mandate
- **WHEN** the inventory carries a mandate ended with `agent-done`
- **THEN** it says the agent reported its work done, and it carries no fulfilment field

### Requirement: The agent is told how to end

The mandate delivered at session start SHALL, for an open `work` mandate with a requester, include one
instruction: when the work is done, answer the requester, then run the done step.

#### Scenario: A started work agent reads its mandate
- **WHEN** an agent-requested `work` agent starts or resumes
- **THEN** its delivered mandate contains the done-step instruction, and a person-started agent's does not

### Requirement: A forgotten work agent is closed after a short bound

A periodic sweep SHALL stop an agent-requested `work` agent whose mandate is open, whose state is measured
`quiet`, that is not in a tool call or at a permission prompt, that has had no operator input later than
its brief, and whose last movement is measured and older than `fleet_idle_close_work_hours` (default 2).
The mandate SHALL be ended with reason `work-idle`, and only after the owner confirms that it found the
agent. Anything unmeasured SHALL keep the agent.

#### Scenario: Answered, then forgotten
- **WHEN** such an agent is quiet, has had no operator input since its brief, and last moved 3 hours ago
- **THEN** the sweep stops it, and its mandate is ended with reason `work-idle`

#### Scenario: The owner took it over
- **WHEN** the operator typed into such an agent after its brief
- **THEN** the sweep keeps it

#### Scenario: Asking or unmeasured
- **WHEN** the agent is asking a person, is in a tool call, or its movement or state is unmeasured
- **THEN** the sweep keeps it

### Requirement: Harness turns are not human input

The human-input measure SHALL NOT count a transcript entry marked `isMeta`, or one whose `origin.kind` is
present and is not `human`. An entry without an `origin` SHALL still be judged by its text, as before.

#### Scenario: A bus watch fires
- **WHEN** an agent's transcript gains a task notification or a stop-hook feedback entry
- **THEN** its last human input does not move

#### Scenario: The operator types
- **WHEN** an entry with `origin.kind: human` and text is appended
- **THEN** it is the last human input
