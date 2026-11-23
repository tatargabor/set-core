## ADDED Requirements

### Requirement: A process inside a held scope is not an orphan

The listing SHALL report an agent as `orphaned` only when its framework scope is NOT held by the owner
at that moment. A process whose scope is held by a live agent SHALL be reported as `foreign`, with no scope.
`recover` SHALL refuse a unit the owner holds before it stops anything.

#### Scenario: A tmux child of a held agent
- **WHEN** a held agent's scope also contains a child agent that the owner does not hold
- **THEN** the child is listed as `foreign` with `scope` null, and no recovery is offered for it

#### Scenario: A genuinely orphaned scope
- **WHEN** an agent runs in a framework scope that the owner does not hold
- **THEN** it is listed as `orphaned` with that scope

#### Scenario: Recover against a held unit
- **WHEN** `recover` is asked for a unit the owner holds
- **THEN** it raises before any stop is attempted

### Requirement: A foreign agent inside tmux carries its pane

For a `foreign` agent, the listing SHALL carry `tmux: {pane, viewer}` only when the process's environment
names a tmux server and pane, AND that server's pid is an ancestor of the process. An environment alone
SHALL NOT be believed.

#### Scenario: Inside a pane
- **WHEN** a foreign agent runs in a tmux pane
- **THEN** its row carries `tmux.pane`, and `tmux.viewer` is null until a viewer is held

#### Scenario: Inherited environment only
- **WHEN** a process carries `TMUX`/`TMUX_PANE` but is not a descendant of the named server
- **THEN** no `tmux` field is carried and the agent stays plainly foreign

### Requirement: The viewer is owner-held and changes nothing about the agent

`POST /api/fleet/agents/{pid}/tmux-view` SHALL re-derive the pane from the pid of a live discovered agent,
start `tmux attach-session -t <pane>` with the server's own binary through the owner, label it
`tmux-<session>`, and return the label. A request for a session that already has a held viewer SHALL return
the existing label instead of starting a second one. The agent SHALL stay `foreign`: on the card, in its
shown name and in idle-close. The terminal's stop control SHALL state that it ends only the viewer.

#### Scenario: Opening a viewer
- **WHEN** the reader clicks the tmux terminal control on a foreign agent inside tmux
- **THEN** a viewer is started and opened as a live terminal under its label, and the agent row reports `tmux.viewer` and `terminal_label` as that label

#### Scenario: The agent keeps its identity
- **WHEN** a viewer is held for a foreign agent
- **THEN** the card edge stays foreign, the tab shows the agent's own name, and idle-close classifies it as unreachable
