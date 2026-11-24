## IN SCOPE
- Resolving a request for a project to the one session that answers for it
- Starting that session when none is live
- Refusing a request that cannot have a desk, with the reason
- Reserving the desk's label
- Stopping a desk that has been quiet

## OUT OF SCOPE
- Routing inside the bus (a bare project name still follows the bus's own rule)
- Resuming an earlier desk session
- Appointing an already-running session as a desk
- Deciding which requests a desk should accept

## ADDED Requirements

### Requirement: A project request resolves to the project's desk and to no other session
Resolution SHALL return the live, framework-held agent whose open mandate has kind `desk` for the project. It SHALL NOT return a session of the project that holds any other mandate or none, whatever that session is doing.

#### Scenario: A live desk exists
- **WHEN** a request is resolved for a project whose desk is live
- **THEN** that desk is returned and no agent is started

#### Scenario: Only working sessions are live
- **WHEN** a request is resolved for a project that has live `work` agents and no desk
- **THEN** none of those agents is returned

### Requirement: The desk is started when none is live
When a project has no live desk, resolution SHALL start one in the project's root with a `desk` mandate naming the requester, the label `<project>-desk`, and the framework's opening line for a desk. Two requests resolved at the same time SHALL lead to one desk.

#### Scenario: No desk is live
- **WHEN** a request is resolved for a registered project with no live desk
- **THEN** an agent is started in that project's root with a `desk` mandate and the desk label, and is returned once it has a bus seat

#### Scenario: Two requests at once
- **WHEN** two requests for the same project are resolved concurrently and no desk is live
- **THEN** exactly one desk is started and both requests resolve to it

### Requirement: A request that cannot have a desk is refused with the reason
Resolution SHALL refuse, start nothing, and name the reason when the project is not registered, is archived, fails the start-location check, is not enrolled on the bus, or is a folder the runtime has never been trusted in. When enrolment or trust cannot be measured, the request SHALL be refused as unmeasured rather than started. When a started desk does not obtain a bus seat within the bound, the request SHALL fail with a class that says so.

#### Scenario: An archived project
- **WHEN** a request is resolved for an archived project
- **THEN** it is refused with the reason `archived` and no agent is started

#### Scenario: A project that is not on the bus
- **WHEN** a request is resolved for a project with no bus hooks installed
- **THEN** it is refused with the reason `not-on-bus`, naming enrolment as the fix, and no agent is started

#### Scenario: A folder the runtime was never trusted in
- **WHEN** a request is resolved for a project whose folder has no recorded trust decision
- **THEN** it is refused with the reason `not-trusted` and no agent is started

#### Scenario: A desk that never becomes reachable
- **WHEN** a started desk has no bus seat when the bound elapses
- **THEN** the request fails with the class `desk-not-ready`

### Requirement: The desk label is reserved
A desk SHALL NOT be renamed. An agent that is not a desk SHALL NOT be started with, or renamed to, the desk label of a registered project.

#### Scenario: Renaming a desk
- **WHEN** a rename is requested for a desk
- **THEN** it is refused

#### Scenario: Taking a desk label
- **WHEN** a `work` agent is started with a registered project's desk label
- **THEN** the start is refused

### Requirement: A quiet desk stops and an unmeasured one is kept
The framework SHALL stop a desk when it has no engagement that is resolving or open, its state is measured as quiet, and its last movement is measured and older than the configured bound. If any of those is unmeasured, the desk SHALL be kept. The stop SHALL mark the mandate ended with the reason `desk-quiet`.

#### Scenario: A desk with nothing open
- **WHEN** a desk has no open engagement and has been measured quiet for longer than the bound
- **THEN** it is stopped and its mandate is marked ended with the reason `desk-quiet`

#### Scenario: A desk with an open engagement
- **WHEN** a desk has an open engagement and has been quiet for longer than the bound
- **THEN** it is kept

#### Scenario: A desk whose movement is unmeasured
- **WHEN** a desk's last movement cannot be measured
- **THEN** it is kept

### Requirement: A desk that is about to stop is marked where the reader stands
The fleet listing SHALL carry, for each framework-held desk for which every stop condition other than the elapsed quiet time already holds, the seconds remaining until the quiet bound is passed and the bound itself. It SHALL carry no such forecast when an open or resolving engagement, a non-quiet state, or any unmeasured input keeps the desk. The tile SHALL show the forecast on the desk's own badge.

#### Scenario: A quiet desk with nothing open
- **WHEN** a desk has no open engagement, is measured quiet, and its last movement is shorter ago than the bound
- **THEN** the listing carries the remaining seconds and the bound for it, and its tile shows that it will close soon unless a request arrives

#### Scenario: A desk with an open engagement carries no countdown
- **WHEN** a desk has an open engagement
- **THEN** the listing carries no close forecast for it

#### Scenario: A desk past the bound
- **WHEN** a desk satisfies every stop condition and its last movement is older than the bound
- **THEN** the forecast's remaining seconds is zero, never negative
