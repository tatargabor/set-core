# fleet-wave-overview Specification

## Purpose
Every known project's wave boards, seen from the fleet: a read-only summary per tracked job
file (counts, current wave, last update, page link), a header chip that carries the blocked and
unreadable counts while closed, and a floating list leading into the project and onto the board
page. Nothing is written and nothing is persisted.

## Requirements

### Requirement: The fleet summarises every known project's wave boards

`GET /api/fleet/waveboards` SHALL read every `docs/waveboard/*.json` file in every project
the fleet's project list knows (the registry and the messaging registry), and return one
entry per file with: the project name, the job, the title, the page URL (null when not
published), the count of items in each of `todo`, `doing`, `done`, `blocked`, `skipped`,
the number of waves, the current wave (the first wave holding an item that is neither
`done` nor `skipped`; null when there is none), and the latest item `updated` value.

The endpoint SHALL NOT write anything, and SHALL NOT return an item's title or note.

#### Scenario: A board's counts and current wave

- **WHEN** a project holds a job file with wave `w0` all done and wave `w1` with one `doing`
  and one `todo` item
- **THEN** the entry counts 1 `doing`, 1 `todo` and the `w0` items as `done`, and names `w1`
  as the current wave

#### Scenario: A finished board

- **WHEN** every item of a board is `done` or `skipped`
- **THEN** its current wave is null

#### Scenario: A project without boards

- **WHEN** a known project has no `docs/waveboard/` directory
- **THEN** it contributes no entry and no error

### Requirement: A board that cannot be read is reported, never dropped

A job file that is not valid JSON, or whose `schema` is not `set-wave-board/1`, SHALL be
returned as an entry marked unreadable with the project, the file's job name and a short
reason — never left out. One bad file SHALL NOT hide the other boards.

#### Scenario: Malformed job file

- **WHEN** one project's job file is not valid JSON and another project's is valid
- **THEN** the response holds an unreadable entry for the first and a full entry for the
  second

### Requirement: The fleet header carries a wave-board chip

The fleet header SHALL show a chip with the number of boards when at least one board
exists. When any board has a `blocked` item the chip SHALL also show the total blocked
count in the failure colour, and when any board is unreadable it SHALL show that count as
well — both visible without opening anything.

#### Scenario: Blocked items are visible on the closed chip

- **WHEN** two boards hold 3 and 11 blocked items
- **THEN** the closed chip shows 14 blocked in the failure colour

#### Scenario: No boards

- **WHEN** no known project has a wave board
- **THEN** no chip is shown

### Requirement: The chip opens a floating list of the boards

Activating the chip SHALL open a list that floats above the layout and moves nothing
under it, closable by an explicit control and by Escape. Each row SHALL show the project
name, the board title, a progress bar split by status, the blocked count, the current
wave, and how long ago an item last changed. The selected project's boards SHALL be
listed first, then the rest by project name.

Activating the project name SHALL select that project on the fleet screen and close the
list. When the board has a page URL, the title SHALL be a link opening it in a new tab;
otherwise the title SHALL be plain text marked as not published.

#### Scenario: Jumping to a project

- **WHEN** the reader activates a row's project name
- **THEN** the fleet selects that project and the list closes

#### Scenario: Opening a board page

- **WHEN** a board has a page URL and the reader activates its title
- **THEN** the board page opens in a new tab

#### Scenario: Unpublished board

- **WHEN** a board's page URL is null
- **THEN** its title is plain text and the row says it is not published

#### Scenario: Selected project first

- **WHEN** the fleet has project B selected and boards exist in projects A and B
- **THEN** B's boards are listed before A's

### Requirement: The summary carries the board's staleness

Each readable entry of `GET /api/fleet/waveboards` SHALL also carry:
- `reviewed`: the job file's `reviewed.at`, or null;
- `manual_open`: the number of items `sync` cannot move, meaning those that are neither `done`
  nor `skipped` and either have no evidence or are `blocked`;
- `commits_since_change`: commits on the project's `HEAD` since the newest of the items'
  `updated` and `reviewed`, or failing both the job's `created` date. Null when it cannot be
  measured;
- `stale`: true when `manual_open > 0` and `commits_since_change` is at least
  `SET_WAVEBOARD_STALE_COMMITS` (default 3).

These SHALL follow the same rule as `set-wave-board stale`. A git failure SHALL make
`commits_since_change` null and `stale` false, never a zero. The endpoint SHALL still write
nothing, and SHALL still return no item title or note.

#### Scenario: A board the repository moved past

- **WHEN** a project's board has one open item with no evidence and the project has 5 commits
  newer than the board's last change
- **THEN** its entry carries `manual_open` 1, `commits_since_change` 5 and `stale` true

#### Scenario: A reviewed board is current

- **WHEN** the same board carries a `reviewed.at` newer than every one of those commits
- **THEN** its entry carries `commits_since_change` 0 and `stale` false

#### Scenario: A project without git

- **WHEN** a board lives in a directory where git cannot count commits
- **THEN** its entry carries `commits_since_change` null and `stale` false

### Requirement: A stale board is marked on the closed chip and in its row

When any board is stale, the closed chip SHALL show the number of stale boards in the warning
colour, beside the blocked and unreadable counts. A stale board's row SHALL show, after its
age, the number of commits since its last change in the warning colour, with a tooltip naming
the number of items only an agent can move. A row that is not stale SHALL look as it did
before. A row whose staleness was not measured SHALL say so in its age tooltip.

#### Scenario: Stale boards are counted while closed

- **WHEN** two of three boards are stale
- **THEN** the closed chip shows 2 stale

#### Scenario: The stale row says by how much

- **WHEN** a stale board has 438 commits since its last change and 4 manual open items
- **THEN** its row shows 438 commits since, and the marker's tooltip names the 4 items

#### Scenario: A current board is unchanged

- **WHEN** no board is stale
- **THEN** the chip shows no stale count and no row shows a marker
