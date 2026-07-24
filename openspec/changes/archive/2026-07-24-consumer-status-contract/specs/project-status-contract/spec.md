## IN SCOPE
- Envelope validation and the failure result it produces instead of raising
- Declaration discovery: repo manifest, operator config, and precedence between them
- The read/write command namespace split and what set-core can and cannot enforce
- Per-command timeouts and the on-demand flag
- The `errorClass` vocabulary set-core itself emits
- The persistence prohibition

## OUT OF SCOPE
- What any project's commands are called or what they return (that is the project's domain)
- HTTP transport (see `project-status-api`)
- Rendering (see `project-status-surface`)
- Executing deployments, or any write set-core originates on its own

## ADDED Requirements

### Requirement: set-core keeps no built-in list of contract commands
The reader SHALL ask exactly the commands the project declares, and SHALL NOT recognise,
require, or default to any command name of its own.

#### Scenario: A project adds a command
- **WHEN** a project adds a command to its manifest
- **THEN** that command SHALL be asked and its answer surfaced with no framework change

#### Scenario: A name that is not declared
- **WHEN** a caller asks for a command absent from the declared read list
- **THEN** the reader SHALL refuse it, and the name SHALL NOT reach `subprocess`

### Requirement: An answer is an envelope, validated before it is trusted
The reader SHALL accept a JSON object carrying `contractVersion`, `ok`, and — when `ok` is
true — `data`, and MAY carry `generatedAt` and `deprecated`.

#### Scenario: Unsupported contract version
- **WHEN** an answer declares a `contractVersion` this set-core does not support
- **THEN** the reader SHALL refuse it rather than guess at its shape

#### Scenario: The project answers that it could not answer
- **WHEN** an answer carries `ok: false`
- **THEN** the reader SHALL carry the project's own reason through, taking `error`, or
  `message` when `error` is absent
- **AND** SHALL produce a result whose reason states plainly that the project reported a
  failure with no reason, when neither field is present

#### Scenario: No failure is ever an empty success
- **WHEN** any validation step fails
- **THEN** the result SHALL carry no `data` at all, so that a gap cannot be rendered as
  `0`, as an empty list, or as success

### Requirement: The declaration is the contract, and the operator outranks the repository
Declarations SHALL be read from the project's repo manifest and from operator
configuration, with operator configuration taking precedence.

#### Scenario: Operator redirects a command
- **WHEN** operator config and the repo manifest both declare a command
- **THEN** the operator's declaration SHALL be used, so that the person present when
  something is wrong can redirect it without editing someone else's repository

### Requirement: Read and write are separate namespaces
Write commands SHALL be declared in their own list, and a command declared in both lists
SHALL be dropped from both and the conflict logged.

#### Scenario: A command claims to be both
- **WHEN** a name appears in both the read list and the write list
- **THEN** neither list SHALL retain it, because a command cannot be safe to open a page
  with and also change something

#### Scenario: The limit of this protection
- **WHEN** a write command is declared only as a read command
- **THEN** set-core SHALL treat it as a read command, since nothing in an answer states
  that it mutates
- **AND** this limit SHALL be documented rather than implied away, because the guard for
  it belongs to the producer

### Requirement: One timeout cannot serve two kinds of question
The reader SHALL support per-command timeouts declared by the project, falling back to a
global default.

#### Scenario: A slow command under a fast global timeout
- **WHEN** a command's declared timeout exceeds the global default
- **THEN** that command SHALL be allowed its declared timeout, so a slow answer is not
  permanently unobtainable — which on screen is indistinguishable from a project that
  cannot answer it

### Requirement: A project may declare a command on-demand
The reader SHALL support commands declared on-demand, which are excluded from a page load
but remain askable by name.

#### Scenario: Page load with an on-demand command declared
- **WHEN** a page load runs the declared read commands
- **THEN** on-demand commands SHALL NOT be run
- **AND** an unasked command SHALL NOT be counted or rendered as a failure

### Requirement: set-core names its own failures, and those names are documented
When set-core cannot obtain an answer it SHALL attach an `errorClass` naming why, drawn
from a closed vocabulary covering: never asked (`not-configured`, `command-not-found`,
`not-a-write-command`, `invalid-argument`); the attempt failed (`spawn-failed`, `timeout`,
`nonzero-exit`, `response-too-large`); the answer could not be trusted (`invalid-json`,
`invalid-envelope`, `missing-version`, `unsupported-version`, `missing-data`); and the
project's own honest refusal (`project-reported-failure`).

#### Scenario: A reason a reader can look up
- **WHEN** any `errorClass` is emitted
- **THEN** it SHALL be named in the integration record, enforced by a gate, because a
  reason nobody can look up is a gap wearing an explanation

#### Scenario: The project's refusal stays distinguishable
- **WHEN** a project answers honestly that it could not answer
- **THEN** the `errorClass` SHALL distinguish that from a fault on set-core's side

### Requirement: set-core reads a project's data and persists nothing derived from it
The reader SHALL NOT write any part of an answer to a file, to state, or to a log.

#### Scenario: Diagnostic logging on a failure path
- **WHEN** a failure is logged
- **THEN** the log SHALL record the shape of the problem and never the content of the
  answer, since the answers carry the project's domain
