# Fleet Dockable Views Specification

## Purpose

Owns how panels are typed and placed on the fleet screen: a view instance docks to an
edge, the agent grid lays itself out in whatever space is left, and nothing hidden by
docking may conceal a failure.

## IN SCOPE
- More than one kind of panel on the fleet screen, each declaring its type
- Docking a view instance to the top, bottom, left or right edge
- The agent grid laying itself out in whatever space docking leaves
- Saying so when a panel type is not recognised

## OUT OF SCOPE
- What any particular view SHOWS — its content, its data source, its actions
- The changes-and-bugs view and its wave scheduling (its own change)
- Worktrees as places a panel can belong to (touches discovery, not layout)
- Free-floating or overlapping panels: docking is to an edge, or nowhere

## Requirements

### Requirement: A panel declares its type
Every panel on the fleet screen SHALL carry a declared type, supplied by whatever
opened it. The screen SHALL NOT infer a panel's type from its contents.

#### Scenario: An agent panel is one type among several
- **WHEN** an agent session is opened on the screen
- **THEN** its panel declares the agent type, and is laid out as one

#### Scenario: An unrecognised type is reported, not rendered as another
- **WHEN** a panel declares a type the screen does not know
- **THEN** the screen states that the type is unrecognised, and does not render it
  as the type it happens to resemble

### Requirement: A view instance can be docked to an edge
The screen SHALL let a person dock a view instance to the top, bottom, left or
right edge, and SHALL remember which edge each docked instance is on.

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

### Requirement: The agent grid fills what docking leaves
The agent tile grid SHALL lay itself out within the area remaining after docked
views have taken their space, and SHALL NOT be given knowledge of what is docked.

#### Scenario: The column choice still means what it said
- **WHEN** a view is docked while the agent grid is set to a given column count
- **THEN** the grid keeps that column count, laid out in the smaller area

#### Scenario: Docking on two edges at once
- **WHEN** views are docked to two different edges
- **THEN** the agent grid fills the area left by both

### Requirement: Docking must not hide a failure silently
A docked or collapsed view SHALL mark, on the edge where the reader is standing,
that it holds something in a failed or blocked state.

#### Scenario: A failure inside a collapsed view is marked outside it
- **WHEN** a docked view is collapsed and holds an item in a failed state
- **THEN** its collapsed edge carries a marker, so the failure is visible without
  expanding the view

#### Scenario: A calm view claims nothing it did not check
- **WHEN** a docked view cannot determine the state of what it holds
- **THEN** it reports that it does not know, rather than showing no marker
