## IN SCOPE
- One entry point into the engine: a command run from the project's own tree
- Every other caller — including the framework's surface — going through that same entry point
- Run state written where a reader can find it without a running service
- Answer intake on the command path, like every other path

## OUT OF SCOPE
- Starting a work unit over HTTP as a separate mechanism (the surface calls the command instead)
- Rendering the state — the surface is a separate concern
- Chaining units automatically
- Notifying a person that a question exists

## ADDED Requirements

### Requirement: The engine is entered by a command run from the project's tree
The engine SHALL be invocable as a command from within a project's own working tree, by an agent
session working there, without a running framework service. The command SHALL NOT require network
access to the framework.

#### Scenario: An agent starts a unit from its own session
- **WHEN** an agent working in a project's tree invokes the command to run the next unit
- **THEN** the unit runs against that tree
- **AND** no framework service needs to be running

#### Scenario: No runnable unit
- **WHEN** the command is invoked and no unit is runnable
- **THEN** it reports why per group and exits without starting anything

#### Scenario: A unit is already running
- **WHEN** the command is invoked while a unit holds the lock for that tree
- **THEN** it refuses and identifies the holder

### Requirement: There is one way into the engine, and every caller uses it
Any other caller that starts a work unit — including the framework's own surface — SHALL do so
through the same command entry point. The engine SHALL NOT expose a second mechanism for starting a
unit.

#### Scenario: The surface starts a unit
- **WHEN** the framework's surface starts a unit for a project
- **THEN** it invokes the same command an agent would invoke
- **AND** the resulting run is indistinguishable from an agent-started one except in what recorded
  who started it

#### Scenario: No parallel start path
- **WHEN** the engine's interfaces are enumerated
- **THEN** exactly one of them starts a work unit

### Requirement: Run state is readable without a running engine or service
The engine SHALL write its run state to a location in the project that a reader can read directly,
so that the framework can report where a run has got to without executing anything and without the
engine still running.

#### Scenario: The framework reads a live run
- **WHEN** a unit is running and the framework is asked where it has got to
- **THEN** it reads the recorded state
- **AND** it does not start a process to find out

#### Scenario: The framework reads a finished run
- **WHEN** a run has finished and its process is gone
- **THEN** the recorded state still reports the outcome of that run

#### Scenario: A stale run is reported as stale
- **WHEN** recorded state claims a run in progress whose process is no longer alive
- **THEN** the reader can tell that state apart from a live run

### Requirement: The command path takes in answers like every other path
The command entry point SHALL perform answer intake before selecting or running a unit, on every
invocation, including invocations that only report state.

#### Scenario: Answer arrives before a command run
- **WHEN** an answer for an awaiting task is placed in the connector and the command is then invoked
- **THEN** the answer is taken in before unit selection
- **AND** the released task's group is eligible to run

#### Scenario: Answer intake on a reporting invocation
- **WHEN** the command is invoked only to report state
- **THEN** answer intake still runs
- **AND** the reported state reflects answers that had arrived
