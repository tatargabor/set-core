# Session Labels Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Meaningful session tab labels
Session tabs show descriptive labels derived from the session's task content instead of generic `#N HH:MM`.

#### Scenario: Session with identifiable task
- **WHEN** a session's first JSONL `enqueue` entry contains a task description (e.g., "# Task\nImplement the cart feature")
- **THEN** the tab label shows a short derived name like "Impl" or "Build fix" or "Verify"
- **THEN** the full task text is available as a tooltip

#### Scenario: Session with gate-related task
- **WHEN** the task text contains "build failed", "fix build", "test", or "verify"
- **THEN** the label reflects the gate: "Build fix", "Test fix", "Verify"

#### Scenario: Fallback for unparseable sessions
- **WHEN** the JSONL cannot be parsed or has no enqueue entry
- **THEN** the tab falls back to `#N HH:MM` format (current behavior)

### Requirement: Session label API
The backend provides session labels alongside session metadata.

#### Scenario: Session list includes labels
- **WHEN** `GET /api/{project}/changes/{name}/session` returns the sessions list
- **THEN** each session object includes a `label` field (string, max 20 chars)
- **THEN** labels are computed from the first JSONL entry's content
