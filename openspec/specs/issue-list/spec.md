# Issue List

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Per-project issue list at /manager/:project/issues
- Cross-project issue list at /manager/issues
- Urgency-based sections (needs attention, in progress, done)
- Filtering by state, severity, source
- Multi-select with bulk actions (group, dismiss)
- Group list section
- Live countdown timers for AWAITING_APPROVAL issues
- Resolved/dismissed section collapsed by default
- Polling every 2 seconds

### Out of scope
- Full-text search across error details
- Pagination (scroll-based, all issues loaded)
- Sorting options (fixed: urgency sections)
- Export to CSV/JSON

## Requirements

### Requirement: Urgency-based sections
The issue list SHALL group issues into three collapsible sections: "Needs Attention" (NEW, DIAGNOSED, AWAITING_APPROVAL), "In Progress" (INVESTIGATING, FIXING, VERIFYING, DEPLOYING), and "Done" (RESOLVED, DISMISSED, MUTED, SKIPPED, CANCELLED, FAILED). The Done section SHALL be collapsed by default.

#### Scenario: Issues grouped by urgency
- **WHEN** the issue list loads with issues in various states
- **THEN** issues appear in the correct section based on their state

#### Scenario: Done section collapsed
- **WHEN** the issue list loads
- **THEN** the Done section is collapsed showing only count, expandable on click

### Requirement: Issue row display
Each issue row SHALL show: checkbox (for multi-select), ID, severity badge, state badge, error_summary (truncated), source, age/time info, group indicator if grouped, and live countdown for AWAITING_APPROVAL.

#### Scenario: Awaiting issue with countdown
- **WHEN** an issue is in AWAITING_APPROVAL state
- **THEN** a live countdown timer shows remaining time until auto-fix

#### Scenario: Cross-project view
- **WHEN** viewing /manager/issues (cross-project)
- **THEN** each row also shows the environment name

### Requirement: Filters
The list SHALL support filtering by state, severity, and source via dropdown selectors. Filters SHALL be applied client-side for responsiveness.

#### Scenario: Filter by severity
- **WHEN** user selects severity=high from the filter dropdown
- **THEN** only high severity issues are displayed

### Requirement: Multi-select and bulk actions
Users SHALL be able to select multiple issues via checkboxes. A bulk action bar SHALL appear with options: "Group Selected" and "Dismiss Selected".

#### Scenario: Group selected issues
- **WHEN** user selects 3 issues and clicks "Group Selected"
- **THEN** a dialog asks for group name and reason, then creates the group via API

### Requirement: Group list
Below the issue list, a groups section SHALL show active groups with their state, name, issue count, and a link to view group detail.

#### Scenario: View group
- **WHEN** user clicks on a group row
- **THEN** the group's issues are highlighted/filtered in the list above
