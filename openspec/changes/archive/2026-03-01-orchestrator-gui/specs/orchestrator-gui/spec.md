## ADDED Requirements

### Requirement: Orchestrator Detail Dialog
The GUI SHALL provide a modeless dialog showing the full orchestration plan status, change details, dependency graph, and action buttons.

#### Scenario: Open dialog from badge
- **WHEN** the user clicks the orchestrator badge `[⚙]` on a project header row
- **THEN** an OrchestratorDialog SHALL open showing the orchestration state for that project
- **AND** the dialog SHALL be modeless (main window remains interactive)

#### Scenario: Dialog header shows plan overview
- **WHEN** the OrchestratorDialog is open
- **THEN** the header SHALL display:
  - Overall status with colored indicator (running/checkpoint/paused/done/failed/stopped)
  - Plan version number
  - Progress ratio (e.g., "3/7 changes done")
  - Total token consumption across all changes
  - Elapsed time since orchestration started

#### Scenario: Dialog refreshes on FeatureWorker update
- **WHEN** the OrchestratorDialog is open
- **AND** the FeatureWorker emits new orchestration data
- **THEN** the dialog SHALL update all displayed values without closing or flickering

#### Scenario: Dialog with no orchestration state
- **WHEN** the user opens the dialog for a project with no orchestration-state.json
- **THEN** the dialog SHALL display "No active orchestration" with a hint to run `set-orchestrate plan`

#### Scenario: Refresh button
- **WHEN** the user clicks "Refresh" in the dialog
- **THEN** the FeatureWorker SHALL immediately re-poll orchestration state
- **AND** the dialog SHALL update within 2 seconds

### Requirement: Change Table
The OrchestratorDialog SHALL display a table of all changes in the plan with per-change details.

#### Scenario: Change table columns
- **WHEN** the change table is rendered
- **THEN** columns SHALL be: Name, Status, Iteration, Tokens, Gates
- **AND** each row represents one change from the orchestration plan

#### Scenario: Change status display
- **WHEN** a change row is rendered
- **THEN** the Status column SHALL show a colored icon and text:
  - `○ pending` (gray)
  - `▶ dispatched` (blue)
  - `● running` (green)
  - `⏸ paused` (gray)
  - `✓ done` (blue)
  - `✓ merged` (green)
  - `✗ failed` (red)
  - `⚠ merge-blocked` (orange)
  - `⚠ stalled` (orange)

#### Scenario: Iteration column
- **WHEN** a change has an active worktree with loop-state.json
- **THEN** the Iteration column SHALL show "current/max" (e.g., "5/30")

#### Scenario: Token column
- **WHEN** a change has token usage recorded
- **THEN** the Tokens column SHALL show the total formatted with comma separators (e.g., "12,340")

#### Scenario: Gates column
- **WHEN** a change has completed the verify gate pipeline
- **THEN** the Gates column SHALL show aggregate gate time in seconds (e.g., "3.2s")
- **AND** tooltip SHALL break down: test, review, verify, build timings and retry count

#### Scenario: Change row tooltip
- **WHEN** the user hovers over a change row
- **THEN** a tooltip SHALL show: full change name, scope text (first 200 chars), worktree path, started/completed timestamps

### Requirement: Dependency Graph Widget
The OrchestratorDialog SHALL include a visual DAG showing change dependencies and their statuses.

#### Scenario: Graph renders change nodes
- **WHEN** the dependency graph widget is displayed
- **THEN** each change SHALL appear as a rounded rectangle node
- **AND** the node SHALL contain the change name (truncated to 20 characters) and a status icon
- **AND** the node background color SHALL match the change status

#### Scenario: Graph renders dependency edges
- **WHEN** change B depends on change A
- **THEN** a directed arrow SHALL be drawn from A's node to B's node

#### Scenario: Graph layout is layered left-to-right
- **WHEN** the graph is rendered
- **THEN** changes with no dependencies SHALL appear in the leftmost column
- **AND** changes with dependencies SHALL appear in columns to the right of all their dependencies

#### Scenario: Graph node tooltip
- **WHEN** the user hovers over a graph node
- **THEN** a tooltip SHALL show: full change name, status, iteration progress, token usage

#### Scenario: Graph scrolling for large plans
- **WHEN** the plan has more nodes than fit in the widget area
- **THEN** the widget SHALL be scrollable (embedded in QScrollArea)

### Requirement: Checkpoint Approval
The GUI SHALL allow developers to approve orchestrator checkpoints without using the CLI.

#### Scenario: Approve button enabled at checkpoint
- **WHEN** the orchestrator status is "checkpoint"
- **THEN** the "Approve Checkpoint" button SHALL be enabled and visually prominent (highlighted color)

#### Scenario: Approve button disabled otherwise
- **WHEN** the orchestrator status is NOT "checkpoint"
- **THEN** the "Approve Checkpoint" button SHALL be disabled and grayed out

#### Scenario: Approve writes to state file
- **WHEN** the user clicks "Approve Checkpoint"
- **THEN** the system SHALL atomically write approval to orchestration-state.json:
  - Set `checkpoints[-1].approved` to `true`
  - Set `checkpoints[-1].approved_at` to current ISO timestamp
- **AND** the write SHALL use temp file + rename for atomicity

#### Scenario: Approve with merge
- **WHEN** the user clicks "Approve + Merge" (if merge queue is non-empty)
- **THEN** the system SHALL write approval with `merge_approved: true`
- **AND** the orchestrator SHALL flush the merge queue on next poll

#### Scenario: Badge blinks at checkpoint
- **WHEN** the orchestrator is in "checkpoint" status
- **THEN** the `[⚙]` badge SHALL blink (yellow/normal toggle) on the existing blink timer

### Requirement: Orchestrator Log Viewer
The OrchestratorDialog SHALL provide quick access to the orchestration log.

#### Scenario: View Log button
- **WHEN** the user clicks "View Log" in the dialog
- **THEN** the `.claude/orchestration.log` file SHALL be opened using the system default text viewer

#### Scenario: View Log when no log exists
- **WHEN** the user clicks "View Log"
- **AND** no `.claude/orchestration.log` exists
- **THEN** a message SHALL inform the user that no log file exists yet

### Requirement: Orchestrator Color Profiles
All orchestrator status colors SHALL be defined in each color profile (light, dark, gray, high_contrast).

#### Scenario: Colors defined per profile
- **WHEN** any color profile is active
- **THEN** the profile SHALL include color values for: `orch_running`, `orch_checkpoint`, `orch_paused`, `orch_done`, `orch_failed`, `orch_pending`, `orch_merged`, `orch_badge_bg`

#### Scenario: Colors are accessible in high contrast mode
- **WHEN** the high_contrast profile is active
- **THEN** orchestrator status colors SHALL have sufficient contrast ratio against the background (minimum 4.5:1)
