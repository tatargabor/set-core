## IN SCOPE
- The survival property an agent started from the fleet is promised.
- The obligation to VERIFY that property at start, per platform, rather than assume it.
- The operations a platform backend must provide: start under a label, enumerate,
  look up by label, stop by name, report whether a label is gone.
- How a backend without a unit registry answers "which agents did I start".

## OUT OF SCOPE
- Where the owner's socket lives and who starts the owner — see `agent-owner-platform`.
- The pty, its replay buffer and its drain, which are the owner's, not the backend's.
- Any promise that an agent survives the OWNER's restart. A pty-attached agent
  cannot: its terminal ends when the process holding the master ends, on every
  platform.

## ADDED Requirements

### Requirement: An agent started from the fleet survives a dashboard restart

An agent started from the fleet SHALL continue running when the dashboard's service
is stopped, restarted or crashes.

This is the property, stated without naming a kernel mechanism. On Linux it is
obtained by starting the agent in a transient systemd scope so it is a sibling of the
dashboard's unit rather than a member of its control group. Any other platform SHALL
obtain it by whatever means that platform provides; the requirement is the outcome,
not the mechanism.

#### Scenario: The dashboard is restarted under a running agent
- **WHEN** an agent has been started from the fleet and the dashboard's service is
  restarted
- **THEN** the agent's process is still alive afterwards

#### Scenario: The dashboard is killed rather than stopped
- **WHEN** the dashboard's service is killed
- **THEN** the agent's process is still alive afterwards

### Requirement: Each backend verifies the survival property at start and refuses when it is absent

A backend SHALL verify, at the moment of starting an agent and before reporting
success, that the started process actually holds the survival property, and SHALL
refuse the start when it does not.

A warning is not sufficient. The surface presents a started agent as one that will
outlive a restart; a start that quietly lacks the property makes the surface state
something false, which is worse than a failed start.

The check is platform-specific because the relationship is: on Linux, that the
agent's control group is not the dashboard's nor a descendant of it. On macOS, where
there are no control groups, the backend SHALL verify the process-level relationship
its own kernel can answer — that the agent is not in the dashboard's process group
and is a session leader of its own session.

#### Scenario: A start that would not survive is refused
- **WHEN** a backend starts an agent and its verification finds the process inside
  the dashboard's own lifetime scope
- **THEN** the start fails with an error naming what was found
- **AND** no agent is reported as started

#### Scenario: The check is measured, not assumed
- **WHEN** a backend reports a start as successful
- **THEN** it has read the started process's actual relationship from the running
  system, not inferred it from the flags it passed at spawn

### Requirement: A backend without a unit registry keeps its own record

A backend SHALL keep its own durable record of the agents it started — label, pid,
and the identifiers its liveness check needs — on any platform whose service manager
does not enumerate them, so that enumeration, lookup by label and stop by name work
after the owner restarts.

The record SHALL be reconciled against the running system when read: an entry whose
process is gone SHALL be reported as gone rather than as running, and the record is
never treated as the authority on liveness.

#### Scenario: Enumeration survives an owner restart
- **WHEN** the owner is restarted and the backend is asked to enumerate agents
- **THEN** agents recorded before the restart whose processes are still alive are
  listed

#### Scenario: A stale entry is not reported as alive
- **WHEN** the record names a label whose process no longer exists
- **THEN** enumeration reports it as gone
- **AND** a lookup by that label reports it as gone

#### Scenario: A recycled pid is not mistaken for the agent
- **WHEN** the record names a pid that now belongs to an unrelated process
- **THEN** the backend does not report the label as alive on the strength of the pid
  alone

### Requirement: The backend API is one shape across platforms

The operations the owner calls SHALL keep one signature and one set of return shapes
across platforms, so that the owner, the API layer and the surface contain no
platform branching.

#### Scenario: Callers do not branch on platform
- **WHEN** the owner starts, enumerates, looks up or stops an agent
- **THEN** it calls the same functions with the same arguments on either platform
- **AND** receives the same result shapes

#### Scenario: A label names the same thing on both platforms
- **WHEN** a label is turned into a backend identifier
- **THEN** the framework's own prefix is applied, so its agents can be told from
  every other process on the machine without keeping a list anywhere
