## MODIFIED Requirements

### Requirement: A view instance can be docked to an edge
The screen SHALL let a person dock a view instance to the top, bottom, left or
right edge, and SHALL remember which edge each docked instance is on, **for the
project that view belongs to**.

#### Scenario: A view is sent to an edge
- **WHEN** a person docks a view instance to an edge
- **THEN** it occupies a band along that edge, and stays there across a reload

#### Scenario: Undocking returns the space
- **WHEN** a docked view instance is undocked or closed
- **THEN** the space it held returns to the area the agent grid lays out in

#### Scenario: A docked view's edge is draggable
- **WHEN** a person drags the divider between a docked view and the rest of the
  screen
- **THEN** the view resizes and the position is stored by the same mechanism and
  in the same document as every other divider

#### Scenario: Docking one project leaves another project's docking alone
- **WHEN** a person docks or undocks a view while looking at one project
- **THEN** no other project's docking changes

## ADDED Requirements

### Requirement: Docking belongs to one project
Docking SHALL be stored and rendered per project. The screen SHALL render the
docking of the project being looked at, and no other. A stored docking SHALL
name the project it belongs to, and a write that names no project SHALL be
refused rather than stored screen-wide.

#### Scenario: Another project's docked view does not render here
- **WHEN** a view is docked in one project and a person looks at another
- **THEN** that band is absent from the second project, and its space belongs to
  the agent grid

#### Scenario: A docking without a project is refused
- **WHEN** a docking write arrives that does not name a project
- **THEN** it is rejected and nothing is stored

#### Scenario: A project with nothing docked is the same as one that never docked
- **WHEN** the last docked view in a project is undocked
- **THEN** the stored document holds no docking for that project

### Requirement: Docking arranged before it was per-project is preserved, not placed
Docking stored before it carried a project SHALL be preserved verbatim and
SHALL NOT be rendered in any project. The system SHALL NOT infer which project
such an entry belonged to.

#### Scenario: The old flat arrangement survives a later write
- **WHEN** docking is stored for a project, and the arrangement is saved again
- **THEN** the pre-existing project-less docking is still in the document,
  unchanged

#### Scenario: The old arrangement is not adopted into whichever project is open
- **WHEN** the screen reads a docking that names no project
- **THEN** it renders nothing docked, rather than placing the band in the project
  currently selected
