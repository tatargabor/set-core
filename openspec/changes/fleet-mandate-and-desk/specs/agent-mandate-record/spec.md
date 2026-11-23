## IN SCOPE
- The durable record of why an agent was started: goal, kind, scope, requester, closing condition
- Refusing an agent-requested start that names no goal
- Reporting an agent with no mandate as having none
- Declaring a mandate after the fact, for any agent
- Telling the agent its mandate at every session start
- Carrying the mandate across an owner restart and a restore
- Keeping the mandate's text out of logs and repositories

## OUT OF SCOPE
- Deciding that a mandate is fulfilled from engine evidence (owned by `agent-goal-closure`)
- Rotating a session in place (owned by `agent-session-rotation`)
- Inferring a goal from a transcript, a label or a declared focus
- Lane vocabularies (feature, bugfix, chore)

## ADDED Requirements

### Requirement: A mandate is recorded in the act of starting
When the framework starts an agent with a goal, it SHALL write a mandate record before the agent is started, in a machine-local store written by the dashboard service. The record SHALL carry an id, the kind (`work` or `desk`), the goal, the scope, the closing condition, the requester, the project, the working directory, the label and the unit. The agent owner SHALL NOT persist any part of it.

#### Scenario: A start with a goal leaves a record
- **WHEN** an agent is started through the fleet with a goal
- **THEN** a mandate record with that goal, kind `work`, the label and the requester exists in the store, and the inventory reports it on that agent

#### Scenario: The record outlives the owner
- **WHEN** the agent owner is restarted while an agent with a mandate keeps running
- **THEN** the inventory still reports the same mandate for that agent

### Requirement: An agent-requested start without a goal is refused
A start request that names a requesting agent and carries an empty goal SHALL be refused, and no agent SHALL be started. A start by the person at the screen MAY carry no goal; the agent is then started with no mandate.

#### Scenario: An agent asks for a peer without saying why
- **WHEN** a start request carries a requester seat and an empty goal
- **THEN** the request is refused with a reason naming the missing goal, and no agent is started

#### Scenario: The person starts a terminal without a goal
- **WHEN** the start form is submitted with an empty goal and no requester
- **THEN** the agent is started and the inventory reports it as having no mandate, with the reason `not-declared`

### Requirement: An agent without a mandate is reported as having none
The inventory SHALL report `mandate` as absent, with a reason, for an agent that has no record. It SHALL NOT derive a goal from the agent's label, its transcript, its declared focus or its working directory.

#### Scenario: A hand-opened agent
- **WHEN** an agent the framework did not start is listed
- **THEN** its mandate is reported as absent with the reason `not-started-here`

#### Scenario: A label that looks like a goal
- **WHEN** an agent with no mandate record has a descriptive label
- **THEN** the inventory reports no mandate and no goal text taken from the label

### Requirement: A mandate can be declared later and says whether the agent was told
The framework SHALL accept a mandate declaration for an agent that has none, record it with the source `declared`, and report whether the declaration reached the agent. A declaration SHALL NOT be reported as delivered unless a carrier delivered it.

#### Scenario: Declaring for a hand-opened agent
- **WHEN** a mandate is declared for an agent the framework did not start
- **THEN** the record exists with source `declared` and `delivered` false, and the screen says the agent has not been told

#### Scenario: Declaring for a framework-started agent
- **WHEN** a mandate is declared for an agent started with the framework's session-start carrier
- **THEN** the mandate is delivered at that agent's next session start and `delivered` becomes true

### Requirement: The agent is told its mandate at every session start
An agent the framework starts SHALL receive its mandate as session-start context — goal, kind, scope, requester, closing condition, and the standing rule for requests outside the mandate — on the first start, after a clear, after a compaction and after a resume. The carrier SHALL write no file into the project's tree and SHALL leave the project's own hooks running.

#### Scenario: First start
- **WHEN** an agent is started with a mandate
- **THEN** its session-start context contains the mandate's goal and the standing rule

#### Scenario: After a clear
- **WHEN** the agent's session is cleared
- **THEN** the new session's session-start context contains the same mandate

#### Scenario: The project's own hooks
- **WHEN** the project declares its own session-start hook
- **THEN** that hook still runs for an agent the framework starts

#### Scenario: The project's tree
- **WHEN** an agent has been started with a mandate and has completed its first turn
- **THEN** no file in the project's tree was added or changed by the carrier

### Requirement: The standing rule for outside requests is an instruction and is reported as one
The delivered mandate SHALL tell the agent to decline, once, a request from another agent that falls outside its mandate, naming the project's desk and the command that reaches it. The framework SHALL NOT report this as a guarantee: a surface that describes scope protection SHALL say it is an instruction unless routing enforces it.

#### Scenario: The delivered text names the desk
- **WHEN** a `work` mandate is delivered
- **THEN** the text names the project's desk and the command for reaching a project

#### Scenario: The screen does not overstate it
- **WHEN** the screen describes how an agent treats outside requests
- **THEN** it describes an instruction given to the agent, not a block

### Requirement: The mandate carries who asked and marks it as a claim
The requester in a mandate SHALL be reported as a claim, because the framework does not verify it. The inventory's parent relation SHALL be read from the mandate when the owner no longer holds the agent. The screen SHALL present a recorded requester as a claim and a process ancestor as measured.

#### Scenario: The requester after an owner restart
- **WHEN** the owner has restarted and an agent with a recorded requester is listed
- **THEN** its parent relation is still reported, with the source `recorded`

#### Scenario: The screen's marking
- **WHEN** an agent's parent comes from the recorded requester
- **THEN** the screen marks it as a claim and does not label it measured

### Requirement: The mandate is carried across a restore
When an agent is restored from the roster, its mandate SHALL continue on the restored agent, and the record SHALL list the new session.

#### Scenario: Restoring an agent that had a mandate
- **WHEN** a recorded session with a mandate is restored
- **THEN** the restored agent reports the same mandate id and goal

### Requirement: An ended mandate is kept and never called fulfilled
When the agent holding a mandate ends, the mandate SHALL be marked ended with a reason and kept for a bounded period. This capability SHALL NOT report a mandate as fulfilled.

#### Scenario: The agent is stopped
- **WHEN** an agent with a mandate is stopped
- **THEN** the mandate is marked ended with the reason `stopped` and is still readable

### Requirement: Mandate text is never logged and never enters a repository
The mandate store SHALL be readable by its owner only. Log lines about a mandate SHALL carry its id, its kind and outcome classes, and SHALL NOT carry its goal, scope or closing condition.

#### Scenario: A start is logged
- **WHEN** a start with a goal is logged
- **THEN** the log line contains the mandate id and kind and none of the goal's text

#### Scenario: The store's permissions
- **WHEN** the mandate store is first written
- **THEN** the file is readable and writable by its owner only
