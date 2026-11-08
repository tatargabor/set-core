## ADDED Requirements

### Requirement: The summary carries the dependency edges between boards

Each readable entry of `GET /api/fleet/waveboards` SHALL also carry:
- `deps_out`: one entry per reference in an item's `depends_on`, with `item`, `on` (`project`, `job`, `item`),
  `status` (the referenced item's status, or null when it is unresolved) and `met` (true only when that status is
  `done`);
- `deps_in`: one entry per reference elsewhere that names an item of this board, with `item`, `by` (`project`, `job`,
  `item`) and `met`;
- `waiting`: the number of items that are neither `done` nor `skipped` and have at least one unmet reference;
- `deps_unresolved`: the number of references in `deps_out` whose target was not found among the boards read.

References SHALL be resolved against the boards of the same read. A reference without a project names the board's own
project. The endpoint SHALL return item ids only, never an item's title or note, and SHALL still write nothing.

#### Scenario: An edge between two projects

- **WHEN** project A's item `a` depends on project B's item `b`, which is `doing`
- **THEN** A's entry lists `a` under `deps_out` with `met` false and counts 1 `waiting`, and B's entry lists `a` under
  `deps_in`

#### Scenario: A dangling reference

- **WHEN** an item depends on a job no project has
- **THEN** the entry's `deps_unresolved` is 1 and that reference's `status` is null

### Requirement: The rows and the chip show the dependencies

A board row SHALL show:
- "waits on N" when `waiting` is above zero;
- "blocks N" when any entry in `deps_in` is unmet.

Each marker's tooltip SHALL list the references as `project/job/item`. When any board has `deps_unresolved` above
zero, the closed chip SHALL show the total in the warning colour. A board without dependencies SHALL look as it did
before.

#### Scenario: A waiting board

- **WHEN** a board's `waiting` is 2
- **THEN** its row shows "waits on 2", and the tooltip names the references

#### Scenario: A dangling reference on a closed chip

- **WHEN** one board has a reference that resolves to nothing
- **THEN** the closed chip shows 1 dangling dependency in the warning colour
