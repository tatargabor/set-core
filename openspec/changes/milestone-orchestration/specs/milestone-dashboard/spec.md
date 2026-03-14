## ADDED Requirements

### Requirement: Phase progress section in HTML report
The HTML report (`generate_report()`) SHALL include a "Milestones" section showing phase progress. Each phase SHALL display: phase number, status (pending/running/completed), number of changes (total/merged/failed), dev server link (if running), and completion timestamp.

#### Scenario: Multi-phase progress display
- **WHEN** orchestration has 3 phases with phase 1 completed and phase 2 running
- **THEN** the report SHALL show a table with phase 1 (green/completed, link to localhost:3101), phase 2 (yellow/running), phase 3 (gray/pending)

#### Scenario: No milestones
- **WHEN** milestones are disabled or plan has no phase assignments
- **THEN** the milestones section SHALL be omitted from the report

### Requirement: Per-phase change grouping in execution section
The existing execution section (change table) SHALL group changes by phase when milestones are enabled. Each phase group SHALL have a header row showing "Phase N" with aggregate stats.

#### Scenario: Grouped display
- **WHEN** milestones are enabled and changes have phase assignments
- **THEN** changes SHALL be grouped under phase headers in the execution table
- **AND** each phase header SHALL show total tokens and merged count for that phase

### Requirement: Dev server link in milestone section
Each completed phase with a running dev server SHALL display a clickable link to `http://localhost:<port>` in the milestone progress table.

#### Scenario: Server running
- **WHEN** phase 1 is completed with server on port 3101
- **THEN** the milestone row SHALL contain a clickable link to `http://localhost:3101`

#### Scenario: Server not running
- **WHEN** phase 1 is completed but server_pid is null or process is dead
- **THEN** the milestone row SHALL show "No server" instead of a link
