# Learnings Web Panel Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- LearningsPanel component as a new Dashboard tab
- Expandable sections for reflections, review findings, gate performance, sentinel findings
- Per-change timeline detail view navigable from Changes tab
- Reflection preview in Worktrees page
- Drill-down from summary to detail for all sections

### Out of scope
- Real-time WebSocket updates for learnings (uses existing REST polling pattern)
- Learnings filtering by date range
- Learnings comparison across runs
- Rule suggestion UI (future capability)

## Requirements

### Requirement: Learnings tab in dashboard
The web dashboard SHALL include a "Learnings" tab that displays all orchestration learning data in a unified view with expandable sections.

#### Scenario: Tab visibility
- **WHEN** the dashboard renders its tab bar
- **THEN** a "Learnings" tab SHALL always be visible (not conditionally hidden)

#### Scenario: Tab content
- **WHEN** the user selects the Learnings tab
- **THEN** the LearningsPanel component SHALL render with sections for Agent Reflections, Review Findings, Gate Performance, and Sentinel Findings

### Requirement: Agent reflections section
The LearningsPanel SHALL display agent reflections grouped by change with expandable content.

#### Scenario: Collapsed reflection
- **WHEN** reflections data is loaded
- **THEN** each reflection shows as a collapsed row with change name, iteration info, and a truncated preview of the first bullet point

#### Scenario: Expanded reflection
- **WHEN** the user expands a reflection row
- **THEN** the full reflection markdown content is shown

#### Scenario: No reflections
- **WHEN** no worktrees have reflections
- **THEN** the section shows "No agent reflections yet"

### Requirement: Review findings section
The LearningsPanel SHALL display review findings with recurring patterns highlighted and per-finding drill-down.

#### Scenario: Recurring patterns banner
- **WHEN** review findings contain patterns appearing in 2+ changes
- **THEN** a "Recurring Patterns" subsection shows each pattern with its occurrence count

#### Scenario: Finding list
- **WHEN** review findings are loaded
- **THEN** findings display as expandable rows with severity badge (CRITICAL/HIGH/MEDIUM), summary text, and change name

#### Scenario: Expanded finding
- **WHEN** the user expands a finding row
- **THEN** the detail shows file path, line number, fix recommendation, and attempt number

### Requirement: Gate performance section
The LearningsPanel SHALL display aggregate gate pass rates and retry costs in a table format.

#### Scenario: Gate stats table
- **WHEN** gate stats data is loaded
- **THEN** a table shows each gate (build, test, review, e2e, smoke) with pass rate (as percentage and fraction), average duration, and retry count

#### Scenario: Retry cost summary
- **WHEN** gate stats include retry data
- **THEN** a summary line below the table shows total retry time and its percentage of total gate time

#### Scenario: Per-change breakdown
- **WHEN** the user expands a "Per change breakdown" row
- **THEN** a breakdown shows each change with its gate results as pass/fail icons and retry count

### Requirement: Sentinel findings section
The LearningsPanel SHALL embed sentinel findings data (reusing the data from the existing sentinel endpoint).

#### Scenario: Findings present
- **WHEN** sentinel findings exist
- **THEN** findings display with severity badge, change name, summary, and status (open/fixed/dismissed)

#### Scenario: No sentinel data
- **WHEN** no sentinel findings exist
- **THEN** the section shows "No sentinel findings"

### Requirement: Per-change timeline detail view
A dedicated timeline view SHALL show state transitions for a single change, navigable from the Changes tab.

#### Scenario: Navigation from Changes
- **WHEN** the user is viewing the Changes tab and clicks a change detail
- **THEN** a timeline sub-view is available showing the change's state progression

#### Scenario: Timeline rendering
- **WHEN** timeline data is loaded for a change
- **THEN** a horizontal flow diagram shows state transitions (pending → running → verify → ...) with timestamps at each node and gate results at verify nodes

#### Scenario: Failed transitions
- **WHEN** a transition goes to a failed state (e.g., verify → failed)
- **THEN** the transition edge shows the failure reason (e.g., "gate:test fail") and the failed node is highlighted in red

#### Scenario: Timeline summary
- **WHEN** the timeline is rendered
- **THEN** a summary line shows total duration, retry count, and total gate runs

### Requirement: Reflection preview in Worktrees
The Worktrees page SHALL show a truncated reflection preview for worktrees that have reflections.

#### Scenario: Worktree with reflection
- **WHEN** a worktree has `has_reflection: true`
- **THEN** the worktree list item shows a truncated first line of the reflection content below the branch info

#### Scenario: Worktree without reflection
- **WHEN** a worktree has `has_reflection: false` or undefined
- **THEN** no reflection preview is shown
