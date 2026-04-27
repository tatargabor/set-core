# Issue Detail

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Slide-out panel (50-60% width) from right side
- Issue header with ID, severity, state, environment, group
- Tabbed content: Timeline (default), Diagnosis, Error, Related
- Diagnosis display with root cause, impact, confidence, fix scope, affected files
- Raw error output display with occurrence count
- Related issues / group view with group actions
- Panel close on Escape or clicking outside

### Out of scope
- Full-page issue detail view (slide-out only, may add full-width toggle later)
- Issue editing (severity, summary) from detail panel
- Inline code viewing of affected files

## Requirements

### Requirement: Slide-out panel
Clicking an issue in the list SHALL open a slide-out panel from the right occupying 50-60% of the viewport width. The issue list SHALL remain visible behind. Pressing Escape or clicking outside SHALL close the panel.

#### Scenario: Open issue detail
- **WHEN** user clicks an issue row in the list
- **THEN** a slide-out panel opens showing the issue detail with Timeline tab active

#### Scenario: Close panel
- **WHEN** user presses Escape while the panel is open
- **THEN** the panel closes and the issue list is fully visible

### Requirement: Issue header
The panel header SHALL show: issue ID, severity badge, state badge, error_summary, environment, source, group (if any), and occurrence count.

#### Scenario: Header with group
- **WHEN** viewing an issue that belongs to GRP-002
- **THEN** the header shows "GRP-002: db-setup-sequence" as a clickable link to Related tab

### Requirement: Diagnosis tab
The Diagnosis tab SHALL display: root_cause, impact, confidence (as percentage), fix_scope, suggested_fix, affected_files (as clickable paths), related_issues, and tags. If no diagnosis exists, it SHALL show "No diagnosis yet — investigation pending or not started".

#### Scenario: Diagnosis available
- **WHEN** viewing an issue with a completed diagnosis
- **THEN** all diagnosis fields are displayed with appropriate formatting

#### Scenario: No diagnosis
- **WHEN** viewing an issue without diagnosis (NEW or INVESTIGATING state)
- **THEN** a placeholder message is shown

### Requirement: Error tab
The Error tab SHALL display the raw error_detail in a monospace code block with syntax highlighting for stack traces. It SHALL show occurrence_count, first seen time (detected_at), and last seen time (updated_at).

#### Scenario: Error display
- **WHEN** viewing the Error tab
- **THEN** the full error output is shown in a scrollable monospace block

### Requirement: Related tab
The Related tab SHALL show the issue's group (if any) with all member issues listed. It SHALL provide buttons: "Fix Group Together" and "Remove from Group". If not grouped, it SHALL show "Not part of a group" with suggested related issues from the diagnosis.

#### Scenario: Grouped issue
- **WHEN** viewing Related tab for an issue in GRP-002
- **THEN** all GRP-002 member issues are listed with their states

#### Scenario: Ungrouped issue with suggestions
- **WHEN** viewing Related tab for an ungrouped issue whose diagnosis has suggested_group
- **THEN** the suggestion is shown with a "Create Group" button
