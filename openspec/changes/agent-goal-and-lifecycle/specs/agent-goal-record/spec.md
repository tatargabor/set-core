## IN SCOPE
- A goal declared at the moment an agent is started by the framework, and held as a framework record
- The goal's kind, resolved through the vocabulary that already owns change lanes
- Reporting the absence of a goal for an agent the framework did not start
- Reading a goal while its agent runs, without touching the agent's transcript
- Surviving a restart of the component that started the agent, because the agent survives it too

## OUT OF SCOPE
- Deciding WHICH goals get handed out, and in what waves (a later change)
- Closing a goal, and what counts as evidence for it (`agent-goal-closure`)
- Rotating an agent's session when its context runs low (`agent-session-rotation`)
- Any goal for a sub-agent a running agent spawns — measured 2026-08-19, such a session writes no
  transcript of its own and the parent records only the act; accounting for those is a later change

## ADDED Requirements

### Requirement: A framework-started agent carries a goal declared when it is started
The framework SHALL record a goal at the moment it starts an agent, and SHALL refuse to start one
without a goal. The record SHALL carry the goal's text, its kind, the identity that requested it, and
when it was declared.

The moment of the act is the only moment this relation exists. Measured on this repository
(`fleet-view` task 2.5): **0 of 23** live agents had an agent ancestor, and an agent the framework
starts has a plain owner process as its parent — so no later traversal of processes, logs or
registries can recover who wanted what. A record written afterwards is a reconstruction.

#### Scenario: The goal is recorded before the agent runs
- **WHEN** the framework starts an agent
- **THEN** a goal record exists carrying text, kind, requester and declaration time
- **AND** it is written before the agent process is able to produce its first turn

#### Scenario: A start without a goal is refused
- **WHEN** a caller asks the framework to start an agent and supplies no goal
- **THEN** the framework SHALL refuse the start
- **AND** it SHALL NOT substitute a default, an empty goal, or the prompt text as a goal

### Requirement: An agent the framework did not start has no goal, and no goal is invented for it
The framework SHALL report an agent it did not start as having **no goal**, and SHALL NOT derive one
from its transcript, its working directory, its branch or its declared focus.

An agent opened by hand in an editor is the ordinary case on a developer's machine, not a defect. A
derived goal would be wrong exactly when the situation is unusual, which is when the screen is being
read — the same reason `fleet-view` refuses to guess a phase.

#### Scenario: A hand-opened session reports an absent goal
- **WHEN** an agent is discovered that the framework did not start
- **THEN** its goal is reported as absent
- **AND** absent is distinguishable from a goal that is empty or unknown

#### Scenario: No goal is inferred from what the agent is doing
- **WHEN** an agent without a goal record is running and its transcript describes work
- **THEN** the framework SHALL NOT present any part of that work as the agent's goal

### Requirement: A goal's kind comes from the lane vocabulary and an unknown kind is refused
The framework SHALL resolve a goal's kind through the vocabulary owned by `change-lane-profiles`, and
SHALL refuse a kind that vocabulary does not define. The framework SHALL NOT define a second set of
agent kinds.

`change-lane-profiles` already owns which change types are valid and already forbids a lane that
resolves to the same behaviour as an existing one. A parallel taxonomy here would be a second copy of
that decision, and it would drift on the day it was written.

#### Scenario: A declared kind resolves through the existing vocabulary
- **WHEN** an agent is started with a kind the lane vocabulary defines
- **THEN** the goal record carries that kind

#### Scenario: An unknown kind is refused rather than defaulted
- **WHEN** an agent is started with a kind the lane vocabulary does not define
- **THEN** the framework SHALL refuse the start
- **AND** it SHALL NOT map the kind to a default lane

### Requirement: A goal outlives the process that recorded it
The goal record SHALL survive a restart of the component that started the agent, and SHALL be
readable for an agent recovered after such a restart. A recovered agent whose goal cannot be
restored SHALL be reported as having an **unrecoverable** goal — distinct both from an agent that
never had one and from an agent whose goal is known.

This is not a general durability preference; it is forced by an asymmetry the framework already
builds in deliberately. A started agent runs in its own transient scope precisely so that it
**outlives** the service that started it, while the record of who asked for it is held in memory —
measured: `AgentOwner` keeps its agents in a dict and writes nothing, and the recovery path takes
`unit`, `session_id`, `cwd`, `label` and `resume_argv` but no requester. So a goal stored the same
way would vanish while the agent it describes keeps working, and the surface would show a running
agent whose purpose the framework has forgotten. That is a false absence about the very field this
capability exists to add.

#### Scenario: A goal survives a restart of the starting component
- **WHEN** the component that started an agent is restarted while the agent keeps running
- **THEN** the agent's goal, kind, requester and declaration time are still readable

#### Scenario: A goal that cannot be restored is named as unrecoverable
- **WHEN** a recovered agent's goal cannot be restored
- **THEN** it is reported as unrecoverable
- **AND** it is not reported as absent, and not reported as a goal with unknown text

### Requirement: A goal is readable while its agent runs, without reading the agent's session
The framework SHALL make a goal record readable at any time during the agent's life, and SHALL read
it from the record rather than from the agent's transcript.

#### Scenario: The goal is readable during the run
- **WHEN** a reader asks for a running agent's goal
- **THEN** the goal is returned from the record
- **AND** answering does not require the agent to be idle or to be asked

#### Scenario: Reading a goal does not read the transcript
- **WHEN** a goal is read for an agent whose session log is present
- **THEN** the session log is not opened as part of answering
