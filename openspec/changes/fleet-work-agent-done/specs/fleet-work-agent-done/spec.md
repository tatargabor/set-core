## ADDED Requirements

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

Idle-close SHALL close an agent-requested `work` agent with no owner input since its start once its last
movement is measured and older than `fleet_idle_close_work_hours` (default 2). Owner input after the
start SHALL put the agent back under the ordinary threshold. Anything unmeasured, or an agent in the
middle of a tool call, SHALL be kept.

#### Scenario: Answered, then forgotten
- **WHEN** an agent-requested `work` agent has had no owner input and its last movement was 3 hours ago
- **THEN** idle-close closes it, and its mandate is ended with reason `stopped`

#### Scenario: The owner took it over
- **WHEN** the owner typed into such an agent after its start
- **THEN** the 48-hour rule applies to it instead

#### Scenario: Movement unmeasured
- **WHEN** the agent's last movement cannot be measured
- **THEN** it is kept
