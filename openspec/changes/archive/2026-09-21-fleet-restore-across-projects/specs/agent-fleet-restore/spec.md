## ADDED Requirements

### Requirement: The fleet offers restore across projects from one dialog

The fleet screen SHALL offer a fleet-wide reopen control that is reachable without selecting a
project and while agents are running. It SHALL sit in the project column's attention row, after
the status marks, and SHALL NOT be drawn when the fleet-wide record lists no project or cannot
be read.

The control SHALL open a single dialog listing every project that has a record, newest first,
each with its recorded count and the age of its newest entry. Opening a project SHALL show its
recorded entries with the same lineage grouping, per-entry selectability, blocked-entry reasons
and peek as the per-project dialog. A project's entries SHALL be read when that project is
opened, not before.

Selection SHALL span projects. The act SHALL be armed: before anything is posted it SHALL state
how many agents it would start and in how many projects, and it SHALL post nothing until
confirmed. Nothing SHALL be selected when the dialog opens, and there SHALL be no act that
restores a whole project or the whole fleet from this dialog.

Each project's selection SHALL be posted to that project's existing restore route with exactly
the selected keys. The result SHALL be shown per project and summed across projects. It SHALL
read as complete only when every project's request succeeded and every project's own result was
complete. A project whose request failed SHALL be named together with its error, and it MUST NOT
be counted as a project where nothing started.

The dialog SHALL close on its close control, on Escape and on a click outside it, and SHALL NOT
close on a click inside it.

#### Scenario: The control is reachable while agents are running

- **WHEN** agents are running and the fleet-wide record lists projects
- **THEN** the project column's attention row shows the reopen control, with no project selected

#### Scenario: No record, no control

- **WHEN** the fleet-wide record lists no project, or its read fails
- **THEN** no reopen control is drawn

#### Scenario: A project's entries are read on opening it

- **WHEN** the dialog opens listing three projects
- **THEN** no per-project record read has been made, and opening one project reads that project's record only

#### Scenario: One click posts nothing

- **WHEN** entries are ticked in two projects and the restore act is clicked once
- **THEN** the dialog states the agent and project counts and no restore request has been sent

#### Scenario: Confirmed selection posts exactly the ticked keys per project

- **WHEN** two entries are ticked in project A and one in project B, and the act is confirmed
- **THEN** A's restore route receives exactly A's two keys, B's receives exactly B's one key, and no other project's route is called

#### Scenario: A failed project makes the whole result partial and is named

- **WHEN** A's restore completes and B's request is answered with a 503
- **THEN** the result is marked partial, A's outcome is shown, and B is named with the error it returned

#### Scenario: A partial project makes the whole result partial

- **WHEN** every project's request succeeds but one project's result is not complete
- **THEN** the cross-project result is marked partial
