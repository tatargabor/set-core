## IN SCOPE
- The view control at the top of the projects screen, and what each view shows
- The same way of looking on the FLEET's project column, where the reader actually stands
- The name filter over the rows, in every view
- The live-session count carried on a project row, and where it comes from
- Rows the fleet measures as live that the project registry does not know
- What the screen must say whenever it is not showing every row it received
- How a missing or failed fleet measurement is rendered

## OUT OF SCOPE
- Grouping, sorting controls, or column selection
- Any change to `GET /api/projects` or `GET /api/fleet/agents` — both are consumed as they ship
- Starting, stopping or otherwise acting on an agent from this screen (that is the fleet's)
- The meaning of the orchestration `status` column, which this change neither fixes nor trusts

## ADDED Requirements

### Requirement: The projects screen SHALL offer a view control, defaulting to the full listing
The screen SHALL present, above the table, a control selecting between at least two views:
an **All** view listing every project the projects endpoint returned, and a **Live sessions**
view listing only projects measured as holding at least one live agent session. The initial
view SHALL be **All**, so that arriving at the screen never silently narrows what it shows.

The control SHALL state the row count each view would show, so the reader learns what the
other view holds without switching to it.

#### Scenario: The screen opens on the full listing
- **WHEN** the projects screen loads
- **THEN** the All view is selected and every project the endpoint returned is listed

#### Scenario: Switching to the live view narrows the rows
- **WHEN** the reader selects the Live sessions view
- **THEN** only projects with at least one live agent session are listed

#### Scenario: Each view names its own size
- **WHEN** the view control is rendered
- **THEN** it shows how many rows All holds and how many rows Live sessions holds

### Requirement: A name filter SHALL narrow the rows in every view
The screen SHALL offer a text filter matching against the project name, case-insensitively,
as a substring. The filter SHALL apply in every view, and SHALL be clearable in one action.

#### Scenario: Typing narrows the table
- **WHEN** the reader types text into the filter
- **THEN** only rows whose name contains that text, ignoring case, are listed

#### Scenario: The filter survives a view switch
- **WHEN** the reader has typed a filter and then switches view
- **THEN** the filter still applies, and the row counts shown reflect it

#### Scenario: Clearing restores the view
- **WHEN** the reader clears the filter
- **THEN** every row of the current view is listed again

### Requirement: The live-session count SHALL be shown in every view, not only the live one
Each project row SHALL carry the number of live agent sessions the fleet measures for it, in
the All view as well as in the Live sessions view. A project with none SHALL be rendered as a
measured zero, distinct from a project whose count could not be measured.

The count is the fact the orchestration `status` column cannot carry: that column has been
measured reporting a project stopped while agents were working inside it. Placing the count
behind a view mode would leave the default screen exactly as misleading as before.

#### Scenario: A live project shows its count in the default view
- **WHEN** the All view is rendered and the fleet measures three live sessions for a project
- **THEN** that project's row shows three live sessions

#### Scenario: A dormant project shows a measured zero
- **WHEN** the fleet measurement arrived and names no session for a project
- **THEN** that project's row shows no live sessions, and does not show an unmeasured marker

### Requirement: A live project the registry does not know SHALL be shown and marked
Where the fleet measures a live session for a project that the projects endpoint did not
return, the Live sessions view SHALL list it, marked as not registered, and SHALL NOT link it
to a project route.

Omitting it would reproduce the exact false absence this screen already produces — a project
with live work in it, missing from the screen that claims to list projects. Rendering it like
any other row would claim a registration that does not exist, and offer a link that leads
nowhere.

#### Scenario: An unregistered live project appears in the live view
- **WHEN** the fleet reports a live session for a project absent from the projects endpoint
- **THEN** the Live sessions view lists it with its session count and a not-registered mark

#### Scenario: The unregistered row is not a link
- **WHEN** an unregistered live row is rendered
- **THEN** it carries no navigation to a project route

#### Scenario: The default view is unchanged by it
- **WHEN** the All view is rendered
- **THEN** it lists what the projects endpoint returned, and unregistered live projects are
  reported by the live view's own count rather than injected into the listing

### Requirement: Rows the screen is not showing SHALL be counted where the reader is standing
Whenever the rendered table holds fewer rows than the screen received — because of the view,
the name filter, or both — the screen SHALL state how many rows are not shown and why, next to
the table rather than only at the control that caused it. Clearing back to the full listing
SHALL be one action.

A view control and a filter are compaction mechanisms whose blast radius is whole rows, and
the reader chose them, which is when a hidden failure is least likely to be looked for.

#### Scenario: A filter states what it hid
- **WHEN** a filter reduces the listed rows
- **THEN** the screen states how many rows are hidden by the filter

#### Scenario: A view states what it hid
- **WHEN** the Live sessions view is selected and projects without a session exist
- **THEN** the screen states how many projects are not shown in this view

#### Scenario: Clearing is one action
- **WHEN** rows are hidden by the view, the filter, or both
- **THEN** a single control returns the screen to the unfiltered All view

### Requirement: An absent fleet measurement SHALL be stated, never rendered as zero
Where the fleet measurement has not arrived or failed, the screen SHALL say so. It SHALL NOT
show live-session counts of zero, and it SHALL NOT present an empty Live sessions view as a
measured absence of live work. Failure of that measurement SHALL leave the All view usable.

#### Scenario: The fleet request fails
- **WHEN** the fleet measurement cannot be read
- **THEN** the screen states that live sessions are unmeasured, and each row's live-session
  cell shows unmeasured rather than zero

#### Scenario: The listing still works without the fleet
- **WHEN** the fleet measurement cannot be read
- **THEN** the All view still lists every project the projects endpoint returned

#### Scenario: The live view does not claim calm it did not measure
- **WHEN** the fleet measurement cannot be read and the reader selects the Live sessions view
- **THEN** the view says the measurement is missing rather than showing an empty list

### Requirement: The fleet's project column SHALL offer the same live way of looking
The project column on the fleet screen SHALL present, above its list, a control selecting
between the reader's **arrangement** (groups, parked, ungrouped — the default) and a **live**
list holding only the projects with at least one live agent session, plus a name filter that
applies to both. Selecting the live list SHALL change no stored arrangement: no project moves,
no order is written, and returning to the arrangement SHALL restore it exactly.

This is where the reader stands. The projects screen answers the same question for someone
arriving cold; the column answers it for someone already working, whose 40-odd arranged
projects run something in a handful of them.

#### Scenario: The column opens on the arrangement
- **WHEN** the fleet screen loads
- **THEN** the column renders the group tree, and claims no hidden rows

#### Scenario: The live list narrows the column
- **WHEN** the reader selects the live way of looking
- **THEN** only projects holding a live agent session are listed, in the reader's own order

#### Scenario: It writes nothing
- **WHEN** the reader switches to the live list and back
- **THEN** no arrangement is saved and the column renders exactly as before

#### Scenario: A typed filter flattens the tree
- **WHEN** the reader types a name filter in either way of looking
- **THEN** the matching projects are listed as one flat list rather than as a group tree with
  most of its rows removed

### Requirement: A live project SHALL reach the live list wherever the arrangement filed it
The live list SHALL be built from the column's whole reading order — every group whether
collapsed or open, the parked section, the ungrouped tail, and projects the arrangement places
nowhere. A project SHALL NOT be absent from it because of where the reader filed it.

A list built from what the tree happens to render would drop exactly the projects the reader
cannot see, which is the population this way of looking exists to surface.

#### Scenario: A live project inside a collapsed group
- **WHEN** a project with a live session sits in a collapsed group
- **THEN** it is listed in the live list

#### Scenario: A live project in the parked section
- **WHEN** a project with a live session is parked
- **THEN** it is listed in the live list

### Requirement: Narrowing the column SHALL NOT narrow its attention header
The attention header above the column SHALL count the whole column in every way of looking —
agents waiting for an answer, work waiting for a human, unknown states, contradicting
declarations, and projects with no measurement at all. Narrowing the list SHALL be stated as a
hidden count, and clearing back to the full arrangement SHALL be one action.

A view that removes a row and its alarm together is the failure `ui-quality.md` names above all
others: a tidy screen reporting calm it has not verified. The rows this view removes are
precisely the agent-less ones — which is the population "waiting for a human" is drawn from.

#### Scenario: An agent-less project awaiting a human
- **WHEN** the live list is selected and a project with no agent is awaiting a human
- **THEN** the project is not listed, and the header still counts it and offers the jump to it

#### Scenario: The narrowing states itself
- **WHEN** the live list or the filter removes projects from the column
- **THEN** the column states how many are not shown, split by cause, with one control to restore

### Requirement: Discovery entries sharing a project name SHALL be merged, never overwritten
Where the fleet answer contains more than one entry for the same project name, every surface
reading it SHALL merge their agents. The last entry SHALL NOT replace the first.

MEASURED 2026-08-24 on the running dashboard: one project arrived twice — the checkout with
five agents, and a worktree of it with none — and keyed assignment let the empty entry win. The
projects screen showed no live sessions for it and dropped it from the live view; the fleet
column read `live 5` while the screen's own header counted agents in 6 projects. Both failed in
the direction that renders running work as idle.

#### Scenario: Two entries, one name
- **WHEN** the fleet answer holds two entries for one project, with 5 agents and 0
- **THEN** the project counts 5 live sessions and appears in every live view

#### Scenario: The surfaces agree
- **WHEN** a project is named twice in the answer
- **THEN** the per-project count and the screen's own project total do not contradict each other
