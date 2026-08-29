## IN SCOPE

- A project declaring extra paths a work unit should read before starting work.
- How a declared path that does not exist is reported.
- The rule that the engine names no reading path of its own beyond the change's own artifacts.

## OUT OF SCOPE

- The change-artifact reading list itself, which `work-unit-engine` already specifies.
- Loading, indexing or summarising the declared material — it is named to the unit, not
  processed by the engine.
- Project rules and hooks, which reach the unit because it runs as a full agent session and
  need no declaration.

## ADDED Requirements

### Requirement: A project may declare where a unit reads from

The project's adoption declaration SHALL accept a list of additional reading paths, relative to
the project tree, and the engine SHALL carry them into the unit's prompt alongside the change's
own artifacts. The two SHALL be distinguishable in the prompt, because one is the work and the
other is background.

#### Scenario: A project declares reading paths

- **WHEN** a project declares additional reading paths and a unit is started
- **THEN** the unit is told about those paths
- **AND** they are presented separately from the change's own artifacts

#### Scenario: A project declares none

- **WHEN** a project's declaration carries no reading paths
- **THEN** the unit reads exactly what it reads today
- **AND** the engine adds no path of its own

### Requirement: A declared path that is not there is reported, not silently dropped

A declared reading path that does not exist SHALL be reported to the caller and recorded on the
run, rather than omitted from the prompt without trace.

#### Scenario: A declared path is missing

- **WHEN** a declared reading path does not exist in the project tree
- **THEN** the start reports which path was missing
- **AND** the run proceeds with the paths that do exist

#### Scenario: Every declared path is missing

- **WHEN** none of the declared reading paths exist
- **THEN** the caller is told that the declaration reached nothing
- **AND** this is distinguishable from a project that declared nothing

### Requirement: A declaration reaches outside the change directory but never outside the project

A declared reading path SHALL be interpreted relative to the project tree and SHALL be refused
if it resolves outside it.

#### Scenario: A path escaping the project tree

- **WHEN** a declared reading path resolves outside the project tree
- **THEN** it is refused and named in the refusal
- **AND** no content from outside the tree reaches the unit's prompt
