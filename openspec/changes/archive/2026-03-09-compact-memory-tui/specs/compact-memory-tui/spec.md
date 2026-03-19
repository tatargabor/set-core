## ADDED Requirements

### Requirement: 3-column ANSI layout
The `set-memory tui` command SHALL render a 3-column layout when terminal width >= 120 characters.

#### Scenario: Wide terminal layout
- **WHEN** `set-memory tui` is run in a terminal with width >= 120 characters
- **THEN** it SHALL render three columns: left (DB stats + usage signals), center (hook overhead + layers + daily trend), right (recent sessions list)

#### Scenario: Narrow terminal fallback
- **WHEN** `set-memory tui` is run in a terminal with width < 120 characters
- **THEN** it SHALL fall back to the existing single-column layout

### Requirement: Project auto-detection
The `set-memory tui` command SHALL auto-detect the current project from the working directory.

#### Scenario: Running from a git project
- **WHEN** `set-memory tui` is run from within a git repository without `--project` flag
- **THEN** it SHALL detect the project name from the git root directory basename and filter all metrics to that project (prefix match)

#### Scenario: Running with explicit project flag
- **WHEN** `set-memory tui --project sales-raketa` is run
- **THEN** it SHALL filter all metrics to sessions whose project name starts with `sales-raketa`

#### Scenario: Running outside a git repo without project flag
- **WHEN** `set-memory tui` is run outside a git repository without `--project` flag
- **THEN** it SHALL show global metrics (all projects) as current behavior

### Requirement: Project name in header
The TUI header SHALL display the active project filter.

#### Scenario: Project-filtered header
- **WHEN** the TUI renders with a project filter active
- **THEN** the header SHALL show `Memory Dashboard — <project>` instead of just `Memory Overview Dashboard`

#### Scenario: Global header
- **WHEN** the TUI renders without project filter
- **THEN** the header SHALL show `Memory Dashboard — all projects`

### Requirement: Recent sessions panel
The right column SHALL display a list of recent sessions for the filtered project.

#### Scenario: Session list rendering
- **WHEN** the TUI renders the right column
- **THEN** it SHALL show up to 15 most recent sessions with: date+time (MM-DD HH:MM), worktree short name, injection count, token count, citation count

#### Scenario: Worktree name abbreviation
- **WHEN** a session's project name matches `<base-project>-wt-<change-name>`
- **THEN** the session list SHALL display `wt-<change-name>` truncated to 22 characters with `..` suffix if needed

#### Scenario: Main repo session display
- **WHEN** a session's project name exactly matches the base project name
- **THEN** the session list SHALL display `(main)` as the worktree name

### Requirement: Column separator rendering
The layout SHALL use box-drawing characters for column separation.

#### Scenario: Column borders
- **WHEN** the 3-column layout renders
- **THEN** columns SHALL be separated by `│` vertical line characters with `┬` and `┴` junction characters at header/footer lines
