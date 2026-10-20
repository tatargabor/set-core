## IN SCOPE

- Deriving a per-agent stage from the agent's project OpenSpec tree (default flow)
- Overriding the flow with a producer-declared stage order (existing project-status contract)
- Joining an agent session to a change and to a position in the flow
- Gap semantics: a gap is reported, never filled or fabricated
- Exposing the resolved stage on the fleet agent payload

## OUT OF SCOPE

- Rendering the stage on screen (covered by `fleet-agent-tree`)
- Any change to the `stageOrder` contract, its validation, or the project-status table's strip
- Persisting derived stage data anywhere
- Non-OpenSpec flows that are not declared by the producer

## ADDED Requirements

### Requirement: The framework derives a default OpenSpec stage for every agent

The framework SHALL resolve, for each live fleet agent whose project root contains an
`openspec/changes/` tree, a stage consisting of a flow (an ordered list of stage names) and a
position in that flow, derived solely from the project's filesystem. The default flow SHALL be
the OpenSpec lifecycle: `proposal`, `design`, `apply`, `verify`, `archive`. The derivation SHALL
require no declaration, configuration, or cooperation from the project.

#### Scenario: A change with unchecked tasks is in apply

- **WHEN** the project has an active change whose `tasks.md` carries at least one unchecked task
- **THEN** the agent joined to that change resolves to flow `[proposal, design, apply, verify, archive]` at position `apply`

#### Scenario: A change without a tasks.md is in design

- **WHEN** the project has an active change directory that has no `tasks.md` yet
- **THEN** the agent joined to that change resolves to position `design`

#### Scenario: A change with every task checked is in verify

- **WHEN** the project's active change has a `tasks.md` whose tasks are all checked
- **THEN** the agent joined to that change resolves to position `verify`

#### Scenario: An archived change is done

- **WHEN** the change the agent is joined to exists only under `openspec/changes/archive/`
- **THEN** the agent resolves to position `archive`, the last stage of the flow

#### Scenario: A proposal-only change is in proposal

- **WHEN** the project's active change directory carries a proposal but no design artifact and no `tasks.md`
- **THEN** the agent resolves to position `proposal`

### Requirement: The stage is joined to the agent through its session

The framework SHALL resolve which change an agent is working on through the agent's session —
using, in order, a work-cycle record binding that session or pid to a change, then the change
name inferred from the session's own record. The stage on the payload SHALL describe the agent's
own change, not the project's aggregate.

#### Scenario: Two agents on different changes get different stages

- **WHEN** two live agents of one project are joined to two different active changes
- **THEN** each agent's payload carries the stage of its own change, and neither stage is
  computed from the other's

#### Scenario: The join is keyed on session identity, not pid

- **WHEN** an agent's process is replaced by a new pid but the session id is unchanged
- **THEN** the resolved stage follows the session, and the change binding survives the pid change

### Requirement: A producer-declared flow replaces the derived flow

When a project's declared project-status answer carries a stage order for a stage field, the
framework SHALL use that declared order as the flow for the project's agents in place of the
default OpenSpec flow, and SHALL resolve the agent's position against the values the producer's
answer carries. The declared order SHALL be read from the declaration alone, never computed from
the values present; a declared stage holding no agent SHALL remain in the flow; a value outside
the declared order SHALL be present and marked, never dropped. A malformed declaration SHALL
yield no flow — never a partial one.

#### Scenario: A declared flow replaces the OpenSpec default

- **WHEN** a project declares `stageOrder: ["triage", "fixing", "shipping"]` and an agent's
  answer carries stage `fixing`
- **THEN** that agent's flow is `[triage, fixing, shipping]` at position `fixing`, and the
  OpenSpec flow is not used for that project's agents

#### Scenario: A value outside the declared order is marked, not dropped

- **WHEN** an agent's stage value does not appear in the project's declared order
- **THEN** the payload carries the value with an outside-the-flow marker, and no declared stage
  is removed from the flow to make room

#### Scenario: A malformed declaration yields no flow

- **WHEN** the declared stage order is not a list, is empty, contains a blank or non-string
  member, or contains a duplicate stage name
- **THEN** no declared flow is resolved for the project, and the default derivation applies
  rather than a partial declaration

### Requirement: A gap is reported, never filled

When the framework cannot resolve a stage for an agent — the project has no OpenSpec tree and no
declared flow, no change is resolvable for the session, or the resolvable change has no
position in the flow — the payload SHALL state the gap explicitly. The framework SHALL NOT
substitute a stage the evidence does not support, and SHALL NOT silently omit the field in a way
that reads as "no work".

#### Scenario: An agent with no resolvable change carries an explicit gap

- **WHEN** an agent's session cannot be joined to any change and the project has no declared flow
- **THEN** the payload carries a stage whose state is a gap, distinguishable from an agent
  resolved at any position, and distinguishable from an agent with nothing started

### Requirement: The stage reaches the fleet agent payload as an additive field

The fleet agents payload SHALL carry the resolved stage on each agent entry as a new field. The
field SHALL be additive: agents and projects for which no stage resolves keep every existing
field unchanged, and a consumer reading the payload without the new field SHALL continue to work.

#### Scenario: An agent with no resolved stage does not disturb existing fields

- **WHEN** the payload is served for a fleet where some agents have no resolvable stage
- **THEN** every agent entry carries all previously specified fields unchanged, and only agents
  with a resolution carry the stage field's resolved shape

#### Scenario: Nothing derived is persisted

- **WHEN** a stage is resolved from a consumer project's tree or declared answer
- **THEN** no value derived from that resolution is written to any file, log, or store that
  outlives the process — with ONE named exception: a bounded in-memory memo on the
  session→change inference, keyed on the record's own fingerprint and holding only the inferred
  change-name slug for seconds, on the same precedent as the status contract's in-memory answer
  cache
