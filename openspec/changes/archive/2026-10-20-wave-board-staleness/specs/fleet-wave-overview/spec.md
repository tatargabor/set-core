## ADDED Requirements

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
