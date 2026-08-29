## IN SCOPE

- Starting a work unit for a change from the screen, and what the screen must show when that
  start is refused.
- Rendering what the engine recorded — per change and per unit — from the record alone.
- Reaching a running unit's terminal in the project's existing dock, and telling a work unit
  apart from a hand-started session there.
- Reading a finished run's persisted stream when no terminal exists any more.

## OUT OF SCOPE

- The engine's own behaviour: dependency resolution, verdicts, gates, commits.
- Starting a bare agent session, which the screen already offers unchanged.
- Editing a change's task file, answering a deferred question, or any write into the project
  other than starting a unit.

## ADDED Requirements

### Requirement: A project's changes and their runnable state are visible before anything is started

For a project the screen knows, the surface SHALL show which changes the engine can drive and,
for each, whether a unit is runnable — and where it is not, the engine's own reason. A project
that has not adopted the engine SHALL be shown as not adopted, with what is missing.

#### Scenario: An adopted project with a runnable change

- **WHEN** the screen shows a project that has adopted the engine
- **THEN** each change is listed with whether a unit is runnable
- **AND** a change that is not runnable carries the engine's reason for it

#### Scenario: A project that has not adopted the engine

- **WHEN** the screen shows a project with no adoption declaration
- **THEN** it is shown as not adopted, naming what is missing
- **AND** no start is offered for it

#### Scenario: Nothing is runnable

- **WHEN** no change in a project has a runnable group
- **THEN** the screen says so and shows the per-group reasons
- **AND** this is distinguishable from a project with no changes at all

### Requirement: A unit is started from the screen through the engine's own entry point

The screen SHALL start a unit only through the framework's unit-start route, which builds the
engine's invocation itself. The screen SHALL NOT offer any field that names a command, an
argument vector, or a label.

#### Scenario: A unit is started

- **WHEN** a person starts a unit for a change from the screen
- **THEN** the run appears among that project's runs
- **AND** the screen shows which change, which group and which seat it belongs to

#### Scenario: The start is refused

- **WHEN** the start is refused — by the engine, by the location check, or because the engine
  command could not be resolved
- **THEN** the refusal is shown where the person acted, in the refusal's own words
- **AND** nothing is shown as started

#### Scenario: The service that holds terminals is unavailable

- **WHEN** the service that would hold the run's terminal is not available
- **THEN** the start control states that it cannot start and what to run to repair it
- **AND** it is not offered as a control that fails when used

### Requirement: A run is readable from what the engine recorded, with no process alive

The surface SHALL render a run from the engine's recorded state alone: its origin, its seat, its
agent session, its verdict, its gate outcome, its commit, and whether it was set aside and on
what condition. A run whose recorded state claims it is in progress while its process is gone
SHALL be shown as stale, distinguishably from a live one.

#### Scenario: A finished run

- **WHEN** a run has finished and its process is gone
- **THEN** its verdict, gate outcome and commit are shown from the record
- **AND** nothing needs to be running for this to render

#### Scenario: A stale claim

- **WHEN** recorded state claims a run in progress whose process is no longer alive
- **THEN** it is shown as stale
- **AND** it is not shown as running

#### Scenario: A run set aside for a person

- **WHEN** a run was set aside because a person must answer
- **THEN** the question and the task it belongs to are shown
- **AND** the run is not shown as failed

#### Scenario: A run that never reported a verdict

- **WHEN** a run ended without reporting a verdict
- **THEN** that is shown as its own state
- **AND** it is not rendered as a run with no outcome yet

### Requirement: A failing run is marked where the reader is standing

Where runs are grouped, collapsed, or placed behind a tab, any run that failed, was set aside,
or is stale SHALL be marked on the container the reader can see, not only in the place it
lives.

#### Scenario: A failure inside a collapsed group

- **WHEN** a project's runs are collapsed and one of them failed
- **THEN** the collapsed container carries a marker for it
- **AND** the marker names how many, not merely that there is one

#### Scenario: Everything is well

- **WHEN** no run failed, was set aside, or is stale
- **THEN** no marker is shown
- **AND** the absence of a marker is not produced by a state the screen failed to read

### Requirement: A running unit's terminal is reachable in the project's dock

A running unit's terminal SHALL open in the project's existing dock, alongside a hand-started
session's, and the two SHALL be distinguishable there without asking anything else. Closing the
view SHALL NOT stop the run.

#### Scenario: Opening a running unit's terminal

- **WHEN** a person opens a running unit from the screen
- **THEN** its terminal appears in that project's dock
- **AND** it is labelled as a work unit, with its change

#### Scenario: Closing the view

- **WHEN** a person closes a running unit's terminal view
- **THEN** the run continues
- **AND** it remains reachable from the project's runs

#### Scenario: A finished run has no terminal

- **WHEN** a person opens a run whose process has ended
- **THEN** the run's persisted stream is shown instead
- **AND** it is labelled as a recording, not as a live terminal

### Requirement: The screen is verified by looking at it

The change SHALL NOT be reported as done on structural counts alone: the screens it touches
SHALL be opened in a browser against the running dashboard and described by what is actually
seen. Where the browser cannot be reached, that verification SHALL be reported as not done.

#### Scenario: The screens are looked at

- **WHEN** the work is claimed complete
- **THEN** each touched screen has been opened and described, including the refused-start and
  empty states
- **AND** the description names what was seen, not that the tests passed

#### Scenario: The browser cannot be reached

- **WHEN** the browser cannot be reached to perform that check
- **THEN** the verification is reported as not done
- **AND** no passing test run is offered in its place
