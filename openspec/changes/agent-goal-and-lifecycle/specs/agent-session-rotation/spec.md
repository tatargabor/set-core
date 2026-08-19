## IN SCOPE
- Reading how much context an agent has left, from what the runtime reports for the model in use
- Writing a handoff and clearing the session in place, through a terminal the framework owns
- Keeping the process, the label and the surface position across the rotation
- Refusing a rotation the framework cannot perform safely, and saying which refusal it is

## OUT OF SCOPE
- Continuing a loop across separate processes by resume — that is `ralph-session-continuation`, a
  different mechanism for a different situation, and this capability must not become a copy of it
- Deciding what a handoff contains; the `handoff` skill already defines that cargo
- Adopting a session the framework did not start — measured 2026-08-17 and refuted (`fleet-view`
  design §6.1): resume forks the running conversation into a branch nothing reports
- What the agent does after it is cleared, beyond receiving its handoff back

## ADDED Requirements

### Requirement: Remaining context is read from the runtime, per model, and an unknown reading never triggers a rotation
The framework SHALL obtain an agent's remaining context from what the runtime reports for the model
that agent is running, and SHALL NOT compute it from a fixed window size. Where no reading can be
obtained, the remaining context SHALL be reported as unknown, and an unknown reading SHALL NOT
trigger a rotation.

Measured 2026-08-19: the runtime hands a hook `context_window` carrying `context_window_size`,
`used_percentage` and `remaining_percentage`, with the size stated **per model**. The fail direction
decides the second half of this requirement — rotating on a reading the framework does not have would
clear a conversation for no established reason, which is destructive; declining to rotate merely
postpones.

#### Scenario: The window size comes from the model in use
- **WHEN** remaining context is read for an agent
- **THEN** the size used is the one the runtime reports for that agent's model
- **AND** no fixed constant participates in the figure

#### Scenario: An unobtainable reading is unknown and inert
- **WHEN** no context reading can be obtained for a running agent
- **THEN** its remaining context is reported as unknown
- **AND** no rotation is prepared or performed on that agent

### Requirement: A handoff is written before the session is cleared, and a failed handoff cancels the rotation
The framework SHALL write the handoff before sending any clear, and SHALL abandon the rotation if the
handoff was not written. It SHALL verify the handoff by its trace on disk, not by the report of
whatever produced it.

The order is the whole safety of this mechanism: a clear that lands before its handoff exists
destroys the context it was meant to carry, and leaves a running agent with no way to know what it
was doing.

#### Scenario: The handoff exists before the clear is sent
- **WHEN** a rotation is performed
- **THEN** the handoff file exists and is non-empty before the clear reaches the terminal

#### Scenario: A handoff that was not written cancels the rotation
- **WHEN** the handoff cannot be written, or is written empty
- **THEN** no clear is sent
- **AND** the agent continues unchanged, with the failed rotation reported

### Requirement: Rotation happens in place — one process, one label, one position, a new session
The framework SHALL rotate a session without replacing the agent's process. After a rotation the
process, its terminal, its label and its position on the surface SHALL be unchanged, and only the
session identity SHALL be new. The agent's goal SHALL survive the rotation unchanged.

Measured 2026-08-19: `/clear` rotates the session id and the transcript inside the same process — pid
and `/proc/<pid>/stat` starttime unchanged across it, one transcript before and two after. So a
successor agent is not needed, and creating one would produce a second seat, a second label and a
tile that moves, for no gain.

#### Scenario: The process survives the rotation
- **WHEN** an agent's session is rotated
- **THEN** the process identity is unchanged, established by more than its process id
- **AND** the terminal the framework holds is not re-created

#### Scenario: The surface position is not replaced
- **WHEN** an agent's session is rotated
- **THEN** the agent keeps its label and its place
- **AND** no second agent appears for the same work

#### Scenario: The goal is not restarted by a rotation
- **WHEN** an agent whose goal is open is rotated
- **THEN** the goal record is unchanged, including its declaration time and requester

### Requirement: Rotation is attempted only where the framework owns the terminal and the agent is between turns
The framework SHALL offer and perform a rotation only for an agent whose pseudo-terminal it owns, and
only when it has established that the agent is not mid-turn. Where either condition is unmet the
rotation SHALL be refused, and the refusal SHALL name which condition failed.

A clear typed into a terminal mid-turn is not a rotation — it is a keystroke landing somewhere the
sender cannot predict. And an agent someone opened in an editor cannot be written to at all: the
kernel forbids injecting into a terminal the sender does not own, which `fleet-view` already
measured for ordinary input.

#### Scenario: A session the framework did not start is not offered rotation
- **WHEN** an agent is discovered that the framework did not start
- **THEN** no rotation control is offered for it
- **AND** the reason given is that the framework does not hold its terminal

#### Scenario: A busy agent is not cleared
- **WHEN** a rotation is due and the agent is mid-turn
- **THEN** the clear is not sent
- **AND** the rotation waits rather than being abandoned or forced

#### Scenario: Turn state that cannot be established blocks the clear
- **WHEN** the framework cannot establish whether the agent is between turns
- **THEN** it SHALL NOT send the clear

### Requirement: Every rotation is recorded, so repeated rotation is visible
The framework SHALL record each rotation against the agent, with when it happened and the reading
that triggered it, and SHALL make the count readable. An agent rotating repeatedly SHALL be
distinguishable from one that has rotated once.

Rotation is a loss of context by design. An agent that rotates every few minutes is not being kept
alive, it is thrashing — and without a count that state is indistinguishable from steady progress.

#### Scenario: A rotation is recorded with its trigger
- **WHEN** a rotation completes
- **THEN** the record carries its time and the context reading that triggered it

#### Scenario: Repeated rotation is visible
- **WHEN** an agent has rotated more than once
- **THEN** the count is readable alongside its goal
