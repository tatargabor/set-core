# Activity Dashboard Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- New "Activity" tab in the web dashboard
- Horizontally scrollable Gantt-style timeline with per-category swim lanes
- Zoomable time axis
- Summary breakdown bars sorted by time
- Hover tooltips with span details
- Auto-refresh and manual refresh
- Terminal/text visual style

### Out of scope
- Per-worktree separate lanes (aggregated view only)
- Drag-to-select time ranges
- Activity data export (CSV, JSON download)
- Comparison between two runs' activity timelines
- Mobile-responsive layout (desktop-first)

## Requirements

### Requirement: Activity tab registration

The system SHALL add an "Activity" tab to the web dashboard.

#### Scenario: Tab appears in tab bar

- **WHEN** the dashboard loads for a project with orchestration data
- **THEN** an "Activity" tab SHALL appear in the tab bar
- **AND** clicking it SHALL render the activity timeline view

#### Scenario: URL-backed tab state

- **WHEN** the user navigates to `?tab=activity`
- **THEN** the Activity tab SHALL be selected on load

### Requirement: Gantt timeline visualization

The system SHALL render a horizontally scrollable Gantt chart with one swim lane per activity category.

#### Scenario: Swim lane rendering

- **WHEN** activity spans exist for categories `implementing`, `gate:build`, `gate:test`, `merge`
- **THEN** each category SHALL have its own horizontal row
- **AND** category labels SHALL be fixed on the left (sticky positioning)
- **AND** the time axis SHALL be displayed along the top

#### Scenario: Span blocks on lanes

- **WHEN** a span exists with `category=gate:test`, `start=T1`, `end=T2`
- **THEN** a colored block SHALL be rendered on the `gate:test` lane from T1 to T2
- **AND** the block width SHALL be proportional to the span duration relative to the time axis scale

#### Scenario: Parallel span intensity

- **WHEN** two spans overlap in time on the same category lane (e.g., two implementing spans from different worktrees)
- **THEN** the overlapping region SHALL show increased visual intensity (darker shade or stacked opacity)
- **AND** a parallelism indicator (e.g., "x2") SHALL be shown

#### Scenario: Gate retry blocks

- **WHEN** a gate has multiple spans (retries) on the same lane
- **THEN** each retry SHALL render as a separate block
- **AND** failed attempts SHALL show a fail marker
- **AND** the passing attempt SHALL show a pass marker

#### Scenario: Empty lanes hidden

- **WHEN** a category has zero spans in the visible time range
- **THEN** that lane SHALL NOT be displayed

### Requirement: Time axis zoom and scroll

The system SHALL support zooming and horizontal scrolling on the time axis.

#### Scenario: Zoom in

- **WHEN** the user clicks the zoom-in control (or uses scroll wheel with modifier)
- **THEN** the time-per-pixel ratio SHALL decrease (showing finer detail)
- **AND** the visible time window SHALL narrow around the current center

#### Scenario: Zoom out

- **WHEN** the user clicks the zoom-out control
- **THEN** the time-per-pixel ratio SHALL increase (showing more time)
- **AND** the visible time window SHALL widen

#### Scenario: Horizontal scroll

- **WHEN** the timeline extends beyond the visible area
- **THEN** the user SHALL be able to scroll horizontally to view earlier or later time periods
- **AND** the category labels SHALL remain fixed (sticky) during scroll

### Requirement: Hover tooltip

The system SHALL show detailed information when hovering over a span block.

#### Scenario: Tooltip content

- **WHEN** the user hovers over a span block
- **THEN** a tooltip SHALL appear showing: category name, change name, start time, end time, duration, and result (pass/fail if applicable)
- **AND** for gate spans, test count or other detail from the span's `detail` field SHALL be shown if available

### Requirement: Breakdown summary

The system SHALL display a breakdown summary showing time spent per category.

#### Scenario: Breakdown bars

- **WHEN** the Activity tab is active
- **THEN** a breakdown section SHALL show horizontal bars for each category
- **AND** bars SHALL be sorted by total time descending
- **AND** each bar SHALL show the category name, total duration, and percentage

#### Scenario: Summary header

- **WHEN** the Activity tab is active
- **THEN** a summary line SHALL show total wall time, total activity time, and parallel efficiency ratio

### Requirement: Data refresh

The system SHALL support periodic and manual refresh of the activity timeline.

#### Scenario: Manual refresh

- **WHEN** the user clicks the refresh button
- **THEN** the activity timeline data SHALL be re-fetched from the API
- **AND** the Gantt and breakdown SHALL update with the new data

#### Scenario: Auto-refresh during live run

- **WHEN** the orchestration is actively running (status is not `done`)
- **THEN** the activity data SHALL auto-refresh periodically (every 30 seconds)
- **AND** the last refresh timestamp SHALL be displayed

#### Scenario: Auto-scroll to now

- **WHEN** the Activity tab loads during a live run
- **THEN** the timeline SHALL auto-scroll to show the most recent activity (right edge)
