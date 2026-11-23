## ADDED Requirements

### Requirement: An idle agent is told apart from an unmatched one by the agent's own evidence
When an agent cannot be joined to a change, the stage resolver SHALL choose between the
`nothing-started` and `join-failed` gaps from evidence about that agent, not from whether
the project holds un-archived changes. An agent with no running work-cycle record whose
session record was read and addresses no change SHALL resolve to `nothing-started`. An
agent whose session record could not be read SHALL resolve to `join-failed` when the
project has work in flight and to `nothing-started` when it has none. An agent that names
a change the producer's declared index does not carry SHALL resolve to `join-failed`.

#### Scenario: An agent working outside any change in a project with open changes
- **WHEN** a project has un-archived changes, and an agent's readable session record
  contains no change invocation and no running work-cycle record binds it
- **THEN** the agent's stage is the `nothing-started` gap, not `join-failed`

#### Scenario: A declared project with work in flight and an idle agent
- **WHEN** the producer declares a flow with a populated change index, and an agent's
  readable session record names no change
- **THEN** the agent's stage is the `nothing-started` gap

#### Scenario: The record cannot be read
- **WHEN** an agent's session record is missing or unreadable and the project has work
  in flight
- **THEN** the agent's stage is the `join-failed` gap

#### Scenario: A named change the index does not carry
- **WHEN** an agent is joined to a change the producer's declared index does not carry
- **THEN** the agent's stage is the `join-failed` gap
