## IN SCOPE
- Running the engine against any registered project without project-specific code in the framework
- What a project declares in order to be driven, and what happens when it declares nothing
- Telling an un-adopted project apart from a finished one
- Driving several projects from one place, with their state kept apart
- Adopting a project without changing how that project already works

## OUT OF SCOPE
- Deploying framework files into a project (the existing install path already does this)
- Any particular project's conventions, tooling or directory layout
- Migrating an existing project's task files into a different format

## ADDED Requirements

### Requirement: The engine carries no project-specific knowledge
The engine SHALL contain no project name, no project path, and no project-specific command, pattern
or directory layout. Everything that varies between projects SHALL reach the engine through the
resolved profile or through the project's own declaration.

#### Scenario: A second project needs no framework change
- **WHEN** the engine is run against a project it has never been run against before
- **THEN** it operates using only that project's resolved profile and declaration
- **AND** no framework code names that project

#### Scenario: Project-specific behaviour arrives through the profile
- **WHEN** two projects need different gate steps
- **THEN** the difference is expressed in their profiles
- **AND** the engine's behaviour is identical in both cases

### Requirement: Adoption is a declaration, and its absence is not guessed
A project SHALL be adopted by declaring what the engine needs — at minimum where its changes live
and what its gate steps are. Where a project declares nothing, the engine SHALL report the absence
rather than substituting a default.

#### Scenario: An undeclared gate is not invented
- **WHEN** an adopted project declares no gate steps
- **THEN** the engine runs no gate and says so
- **AND** it does NOT fall back to a command it guessed from the project's contents

#### Scenario: A missing declaration is named
- **WHEN** the engine is asked to run against a project that has not declared where its changes live
- **THEN** it refuses and names the missing declaration

### Requirement: An un-adopted project is distinguishable from a finished one
The engine SHALL distinguish "this project has not been adopted" from "this project has nothing to
run". A project that has never been adopted SHALL NOT be reported in terms that a reader would take
to mean its work is complete or that nothing is pending.

#### Scenario: Un-adopted project queried
- **WHEN** the state of a project that has not been adopted is queried
- **THEN** the response states that the project is not adopted
- **AND** it does NOT report zero runnable groups as though the project were up to date

#### Scenario: Adopted project with no open work
- **WHEN** the state of an adopted project with no open tasks is queried
- **THEN** the response distinguishes this from the un-adopted case

### Requirement: Several projects are driven from one place, with state kept apart
The engine SHALL accept the project as an input on every operation, and SHALL keep each project's
lock, run state and pending answers separate. An operation naming one project SHALL NOT affect
another.

#### Scenario: Concurrent projects
- **WHEN** work units are running for two different projects at once
- **THEN** each holds its own lock
- **AND** neither project's state, answers or verdicts appear in the other's

#### Scenario: An answer reaches only its own project
- **WHEN** an answer is submitted naming a change in one project
- **THEN** a task of the same name in another project is unaffected

#### Scenario: A failure in one project does not stop another
- **WHEN** a work unit fails or is blocked in one project
- **THEN** operations against other projects continue to be accepted

### Requirement: Adoption does not require the project to change how it works
Adoption SHALL NOT require a project to restructure its existing task files, rename its artifacts, or
adopt annotations it does not already use. A task file carrying no dependency annotations SHALL be
drivable under the serial default.

#### Scenario: Task file without dependency annotations
- **WHEN** a project's task file carries groups but no dependency annotations
- **THEN** the engine drives it under the serial default
- **AND** it requires no edit to that file before the first run

#### Scenario: Existing conventions are honoured, not replaced
- **WHEN** an adopted project already marks tasks in its own established way
- **THEN** the engine reads those markings rather than requiring a different notation
