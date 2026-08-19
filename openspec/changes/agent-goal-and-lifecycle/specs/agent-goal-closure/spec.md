## IN SCOPE
- Closing a goal on evidence the framework can check itself
- Declaring, at the moment a goal is made, whether its fulfilment is checkable at all
- Stopping a completed agent and releasing its seat
- Keeping the goal and its closing evidence after the agent is gone

## OUT OF SCOPE
- Defining what a completed unit of work is — that is the work unit's verdict, reused here
- Deciding what happens next once a goal closes (a later change)
- Rotating a session that has run low on context (`agent-session-rotation`)
- Persisting anything derived from the agent's conversation, which stays forbidden

## ADDED Requirements

### Requirement: A goal is closed by checkable evidence, never by the agent's report
The framework SHALL close a goal only on evidence it can verify itself, and SHALL NOT close one
because the agent reported completion. Where the goal names work the work-unit engine ran, the
framework SHALL reuse that unit's verdict **diffed against the tree** as the evidence, and SHALL NOT
define completion a second time.

Measured and already written into `.claude/rules/evidence-discipline.md`: an unflagged agent asked to
create a file replied `Done.` with exit 0 and the file did not exist. A gate that waits on an action
measures the action's trace, never the report.

#### Scenario: A completion claim without matching evidence leaves the goal open
- **WHEN** an agent reports that its goal is complete
- **AND** the framework's own check of the evidence does not agree
- **THEN** the goal remains open
- **AND** the disagreement is reported, naming what was claimed and what was found

#### Scenario: Closure reuses the work unit's verdict
- **WHEN** a goal names work the engine ran as work units
- **THEN** the framework closes it from the engine's verdict checked against the tree
- **AND** it does not apply a second, separate definition of completion

### Requirement: A goal whose fulfilment cannot be checked is declared so when it is made
The framework SHALL require every goal to declare, at declaration time, whether its fulfilment is
checkable. A goal declared unverifiable SHALL remain open until a person closes it, and SHALL NOT be
closed by any automatic path.

The declaration is made up front on purpose. Deciding at closing time that a goal was unverifiable
would turn every failed check into a reason to close, which is precisely the direction that costs.

#### Scenario: An unverifiable goal is never closed automatically
- **WHEN** a goal declared unverifiable has been running and its agent reports it finished
- **THEN** the goal stays open
- **AND** it is presented as awaiting a person, not as stalled

#### Scenario: Verifiability is not reassigned after the fact
- **WHEN** a goal declared checkable fails its evidence check
- **THEN** the framework SHALL NOT reclassify it as unverifiable

### Requirement: A closed agent stops and releases its seat
The framework SHALL stop an agent whose goal has closed, and SHALL release the seat it held. An agent
that stopped without its goal closing SHALL be distinguishable from one that completed.

An agent still holding a seat after its work is done is the orphan the fleet surface exists to make
visible; creating that orphan here would defeat the screen this record feeds.

#### Scenario: Completion stops the agent
- **WHEN** a goal closes on verified evidence
- **THEN** the agent is stopped and its seat released

#### Scenario: A stop without closure is not reported as completion
- **WHEN** an agent's process ends while its goal is still open
- **THEN** it is reported as ended with an open goal
- **AND** it is not reported as complete, idle, or successful

### Requirement: The goal record outlives the agent and carries no session content
The framework SHALL keep a goal and its closing evidence readable after the agent has ended, and
SHALL NOT persist anything derived from the agent's conversation alongside it — not the transcript,
not an excerpt, not a summary of it.

The boundary is persistence rather than naming (see `External Project Confidentiality`): an agent's
session is the densest domain source there is, and a closing summary is the natural place for it to
leak.

#### Scenario: The record survives the agent
- **WHEN** an agent has ended
- **THEN** its goal, its kind, its requester and its closing evidence remain readable

#### Scenario: No conversation content is written with the closure
- **WHEN** a goal is closed
- **THEN** what is written references the evidence by identity — a commit, a task marker, a verdict
- **AND** no line of the agent's transcript is copied into the record, a cache, or a log
