## MODIFIED Requirements

### Requirement: A view instance can be docked to an edge
The screen SHALL let a person dock a view instance to the top, bottom, left or
right edge, and SHALL remember which edge each docked instance is on.

A view docked to an agent SHALL follow that agent across a rename and across a restore
after a reboot. The stored dock names an agent, and the name is the framework's label —
so an act that changes the label SHALL carry the dock with it rather than leaving a dock
pointing at a name nothing holds.

A dock that names an agent which genuinely is not running SHALL still be kept and SHALL say
so. That state stays, because an agent can legitimately be absent; what must stop is
reaching it as a *consequence* of the framework renaming or restoring the agent itself.

#### Scenario: A view is sent to an edge
- **WHEN** a person docks a view instance to an edge
- **THEN** it occupies a band along that edge, and stays there across a reload

#### Scenario: A dock follows its agent across a restore
- **WHEN** an agent docked to an edge is lost to a reboot and then restored under its recorded label
- **THEN** the docked view holds that agent again, on the same edge

#### Scenario: A dock follows its agent across a rename
- **WHEN** an agent docked to an edge is renamed
- **THEN** the docked view holds the same agent, on the same edge, under the new name

#### Scenario: A dock whose agent is genuinely absent is kept and says so
- **WHEN** a docked agent is not running and has not been renamed or restored
- **THEN** the panel is kept and states that no running agent has that terminal

#### Scenario: Undocking returns the space
- **WHEN** a docked view instance is undocked or closed
- **THEN** the space it held returns to the area the agent grid lays out in

#### Scenario: A docked view's edge is draggable
- **WHEN** a person drags the divider between a docked view and the rest of the
  screen
- **THEN** the view resizes and the position is stored by the same mechanism and
  in the same document as every other divider
