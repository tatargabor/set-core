## ADDED Requirements

### Requirement: Items carry an assignee chosen from the board's list

A job file SHALL carry a board-level `assignees` list of names and MAY carry an item-level
`assignee`. `init --assignees`, `assignees`, `add --assignee` and `assign` SHALL maintain them;
`assign <job> <item> -` SHALL clear the item's assignee. Both fields SHALL be part of the payload.
No command SHALL write a machine name into the job file or the payload; a legacy item `by` SHALL
be dropped on the next write.

#### Scenario: Assign and clear

- **WHEN** `assign job H1 András` runs and then `assign job H1 -`
- **THEN** the item first has `assignee: "András"` and then no assignee, and each change marks the
  payload for a push

#### Scenario: No hostname reaches the payload

- **WHEN** `sync` runs on a job file whose items still carry `by`
- **THEN** the written job file and payload contain no `by` on any item

## MODIFIED Requirements

### Requirement: The board page is read-only and works offline

The page SHALL render waves, items and status chips, done and remaining counts per wave and
overall, and the last sync time. It SHALL NOT show a machine name. It SHALL subscribe to
`board/state` through the `db` capability and SHALL fall back to the embedded `<script
type="application/json" id="seed">` when the database is unavailable. Each item SHALL offer the
board's `assignees` in a select, showing the `board/assignees` document's value for that item over
the item's own `assignee`. The page's only write SHALL be the `board/assignees` document; it SHALL
NOT write `board/state`. `set-wave-board render` SHALL produce the page with the current payload as
the seed.

#### Scenario: Offline render

- **WHEN** `render <job> -o board.html` runs and the file is opened without the platform
- **THEN** the page shows the job from the seed and says it is a snapshot

#### Scenario: A viewer picks an assignee

- **WHEN** a viewer chooses "Gábor" on item H1 while the database is available
- **THEN** `board/assignees` gets `H1: "Gábor"`, every open view shows Gábor on H1, and a later
  push of `board/state` does not undo it
