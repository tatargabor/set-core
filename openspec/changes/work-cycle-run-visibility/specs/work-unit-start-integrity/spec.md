## IN SCOPE

- Resolving the engine command in the environment the started child will actually run in,
  before anything is claimed on the caller's behalf.
- What a caller is told when the command cannot be resolved, and what it is told when the
  child fails to become the engine for any other reason.
- The ordering between resolution, claiming a scope, and answering the caller.

## OUT OF SCOPE

- How the framework's console scripts get installed onto a machine (packaging, not behaviour).
- Starting a bare agent session, which keeps its own start path unchanged.
- What the engine does once it is running — the unit lifecycle is `work-unit-engine`'s.

## ADDED Requirements

### Requirement: A start is reported as started only when the child could become the engine

The system SHALL NOT report a work unit as started unless the command it started can be
executed in the environment the child runs in. Resolution SHALL be performed against that
environment — not the caller's, and not the environment of the process handling the request —
because those can differ and have been measured to differ.

#### Scenario: The engine command cannot be resolved in the child's environment

- **WHEN** a work-unit start is requested and the engine command does not resolve in the
  environment the child would run in
- **THEN** the request is refused
- **AND** no scope, label, or process identifier is reported for it
- **AND** the refusal names the command that could not be resolved and the environment it was
  looked for in

#### Scenario: The engine command resolves

- **WHEN** the engine command resolves in the child's environment
- **THEN** the start proceeds and the response carries the label, the process identifier, and
  the argument vector that was run

#### Scenario: The refusal names the cause, not the symptom

- **WHEN** a start is refused because the engine command could not be resolved
- **THEN** the refusal names the missing command
- **AND** it does not report the failure as a scope, unit, or service that did not become
  active, which is a true statement about the symptom that points away from the repair
- **AND** the caller is not made to wait for a liveness timeout to learn it

#### Scenario: A caller's environment that differs from the child's does not decide the answer

- **WHEN** the engine command is resolvable in the environment of the process handling the
  request but not in the child's
- **THEN** the start is refused
- **AND** the refusal is the same one as if neither could resolve it

### Requirement: Resolution happens before anything is claimed

The system SHALL resolve the engine command before claiming a scope, a label, or a terminal for
the run. A failure discovered after a claim SHALL release what was claimed.

#### Scenario: An unresolvable command leaves nothing behind

- **WHEN** a start is refused because the engine command could not be resolved
- **THEN** no label is held, no scope exists for that unit, and a subsequent start of the same
  unit is not refused as already running

#### Scenario: The child fails to exec for a reason resolution cannot predict

- **WHEN** the child fails to become the engine after the scope was claimed
- **THEN** the claim is released
- **AND** the caller is told the start failed, with the child's exit status, rather than being
  told it succeeded

### Requirement: One command name, checkable against the engine's own parser

The system SHALL build the engine's argument vector itself rather than accepting one from a
caller, and the command name and starting subcommand SHALL be stated in one place that a test
can check against the engine's own command-line parser.

#### Scenario: The argv is built, never supplied

- **WHEN** a caller requests a work-unit start
- **THEN** no field of that request can name the command, the subcommand, or an arbitrary
  argument

#### Scenario: A subcommand that no longer starts a unit is caught

- **WHEN** the engine's parser no longer recognises the named starting subcommand as one that
  starts a unit
- **THEN** the check fails, rather than the mismatch surviving until a run is attempted
