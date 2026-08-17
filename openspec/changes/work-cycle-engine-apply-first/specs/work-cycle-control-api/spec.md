## IN SCOPE
- Starting one work unit for a change over the manager API
- Answering an open decision over the manager API
- Reporting what is runnable, what is awaiting an answer, and what is currently running
- Refusing an unstartable request with a reason a surface can display

## OUT OF SCOPE
- Rendering any of this — the surface is a separate concern
- Chaining units automatically (later change)
- Changing any existing endpoint's shape
- Delivering a question to a person (notification is the caller's concern)

## ADDED Requirements

### Requirement: A work unit can be started over the API
The API SHALL expose an operation that starts one work unit for a named change, optionally targeting
a specific group, and SHALL return the identity of the started unit. The operation SHALL return as
soon as the unit is started, rather than waiting for it to finish.

#### Scenario: Starting the next runnable unit
- **WHEN** a start request is made for a change with a runnable group
- **THEN** the engine starts that group as a work unit
- **AND** the response identifies the change and the group started

#### Scenario: Targeting a specific group
- **WHEN** a start request names a group
- **THEN** that group is started if it is runnable

#### Scenario: The call does not block on the run
- **WHEN** a work unit is started over the API
- **THEN** the response is returned before the unit completes

### Requirement: An unstartable request is refused with a reason
The API SHALL refuse a start request that cannot be satisfied, and SHALL state which condition
failed — no runnable group, dependencies unsatisfied, awaiting an answer, or a unit already running
for that tree.

#### Scenario: Nothing runnable
- **WHEN** a start request is made and no group is runnable
- **THEN** the request is refused with a reason naming the blocking condition per group

#### Scenario: Already running
- **WHEN** a start request is made while a unit holds the lock for that tree
- **THEN** the request is refused and the response identifies the running unit

#### Scenario: Targeted group is not runnable
- **WHEN** a start request names a group whose dependencies are unsatisfied
- **THEN** the request is refused and the unsatisfied dependencies are named

### Requirement: An open decision can be answered over the API
The API SHALL expose an operation that answers an open decision for a named change and task. An
answer submitted this way SHALL reach the engine through the same connector as any other answer, so
that no answer path is privileged.

#### Scenario: Answering releases the task
- **WHEN** an answer is submitted for a task awaiting a human
- **THEN** the task is no longer reported as awaiting
- **AND** its group becomes runnable if nothing else blocks it

#### Scenario: Answering an unknown task
- **WHEN** an answer is submitted for a task that is not awaiting an answer
- **THEN** the request is refused with a reason

#### Scenario: The API answer uses the ordinary connector
- **WHEN** an answer is submitted over the API
- **THEN** it is delivered through the same answer connector other uploaders use

### Requirement: The state a surface needs is queryable
The API SHALL report, for a change: which groups are runnable, which are awaiting an answer and with
what question, which are blocked and by what, and whether a unit is currently running and how far it
has got.

#### Scenario: Awaiting decisions are listed with their questions
- **WHEN** the state of a change is queried
- **THEN** each task awaiting a human is listed with the question recorded for it

#### Scenario: A running unit is reported with its progress
- **WHEN** a unit is running for the change
- **THEN** the response identifies it and reports progress derived from completed task markers

#### Scenario: A stale run is not reported as running
- **WHEN** a lock exists whose holding process is no longer alive
- **THEN** the response distinguishes that state from a live run
