## MODIFIED Requirements

### Requirement: Worktree List Display
The GUI SHALL display worktrees in a 6-column table: Name, PID, Status, Skill, Ctx%, Extra.

#### Scenario: Table columns
- **GIVEN** the table is displayed
- **WHEN** rendering column headers
- **THEN** the columns are: Name, PID, Status, Skill, Ctx%, Extra (6 total)
- **AND** Name merges former "Project" and "Change" columns
- **AND** PID shows the claude process ID per agent row

#### Scenario: Name column content for worktree rows
- **GIVEN** a local worktree row is rendered
- **WHEN** the Name column is populated
- **THEN** it shows the change ID / branch name (with star prefix for main repo)

#### Scenario: Name column content for team rows
- **GIVEN** a team worktree row is rendered
- **WHEN** the Name column is populated
- **THEN** it shows `member: change_id` (with lightning prefix for own machines)

#### Scenario: Extra column replaces J column
- **GIVEN** the table is displayed
- **WHEN** rendering the last column
- **THEN** the column header is "Extra" instead of "J"
- **AND** it contains Ralph indicator (R button)

#### Scenario: Project grouping
- **GIVEN** worktrees exist across multiple projects
- **WHEN** the Control Center displays the worktree list
- **THEN** worktrees are grouped by project with header rows spanning all columns
- **AND** each agent gets its own row with independent PID, Status, Skill, Ctx%

#### Scenario: Project header badges
- **GIVEN** a project header row is rendered
- **WHEN** the project has orchestration-state.json
- **THEN** an `[⚙]` badge SHALL appear alongside existing `[M]` and `[O]` badges
- **AND** the badge color SHALL reflect the orchestrator status (green=running, yellow=checkpoint, gray=paused/stopped, blue=done, red=failed)
- **AND** clicking the badge SHALL open the OrchestratorDialog for that project

#### Scenario: Orchestrator badge tooltip
- **GIVEN** the orchestrator badge is visible
- **WHEN** the user hovers over the `[⚙]` badge
- **THEN** a tooltip SHALL show a one-line summary: "Orchestrating: X/Y done, Z running" plus checkpoint status if applicable

#### Scenario: Orchestrator badge absent when no orchestration
- **GIVEN** a project has no orchestration-state.json
- **WHEN** the project header row is rendered
- **THEN** no `[⚙]` badge SHALL appear

#### Scenario: Sorting within groups
- **GIVEN** multiple worktrees in a project
- **WHEN** displayed in the list
- **THEN** main repo appears first, then sorted alphabetically by change ID

#### Scenario: Multi-agent rows
- **GIVEN** a worktree has multiple agents
- **WHEN** displayed in the table
- **THEN** each agent is a separate row; primary row has Name + Extra, secondary rows have empty Name/Extra
- **AND** all agent rows map back to the parent worktree for focus/context-menu actions

#### Scenario: Per-agent Ctx%
- **GIVEN** a worktree has N agents with N session files
- **WHEN** Ctx% is calculated
- **THEN** agent[i] reads from the (i+1)th-freshest session file

#### Scenario: Worktree with no editor dimmed
- **WHEN** a worktree has `editor_open: false` in the status data
- **AND** the worktree has no active agents
- **THEN** the row text SHALL be rendered with reduced opacity or gray color

## ADDED Requirements

### Requirement: FeatureWorker Orchestration Polling
The FeatureWorker SHALL poll orchestration state for each registered project.

#### Scenario: Poll orchestration-state.json
- **WHEN** the FeatureWorker runs its periodic poll cycle
- **THEN** for each project it SHALL check for `orchestration-state.json` in the project root
- **AND** if found, parse and include it in the `features_updated` signal under the `orchestration` key

#### Scenario: No orchestration state file
- **WHEN** the FeatureWorker polls a project with no orchestration-state.json
- **THEN** the `orchestration` key for that project SHALL be `None`

#### Scenario: Malformed state file
- **WHEN** the FeatureWorker encounters an unparseable orchestration-state.json
- **THEN** it SHALL log a warning and set the `orchestration` key to `None`
- **AND** the poll cycle SHALL continue without crashing
