## ADDED Requirements

### Requirement: The role file may declare flows between projects
A project's entry in the role file MAY carry a list of flows, each naming the project it goes to, what is passed, and how. A flow SHALL be declared once, on the side it starts from.

#### Scenario: A project with a flow
- **WHEN** a project's entry declares a flow to another registered project
- **THEN** the flow is read with its target, its subject and its manner

#### Scenario: A flow to an unregistered project
- **WHEN** a flow names a project that is not in the registry
- **THEN** the role check reports it as a warning and the rule is still generated without that flow

### Requirement: The generated rule tells the agent how to reach a neighbour
The generated rule SHALL list, for the project's own flows and for flows that reach it, what each is for and which project to ask, together with the command that asks a project. In a public repository's rule a private neighbour SHALL be counted and not named.

#### Scenario: A rule with flows
- **WHEN** the rule is generated for a project that declares flows
- **THEN** it contains each flow's subject and target, and the command for asking a project

#### Scenario: A public repository with a private neighbour
- **WHEN** the rule is generated for a public repository whose flow goes to a private project
- **THEN** the private project is counted and its name does not appear

#### Scenario: A project with no flows
- **WHEN** the rule is generated for a project that declares no flows and is reached by none
- **THEN** the rule still contains the command for asking a project
