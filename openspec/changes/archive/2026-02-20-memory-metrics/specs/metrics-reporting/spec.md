## ADDED Requirements

### Requirement: TUI metrics report command
The `set-memory metrics` command SHALL read the SQLite database and print a formatted text report to stdout.

#### Scenario: Default report (last 7 days)
- **WHEN** `set-memory metrics` is run without arguments
- **THEN** it SHALL display metrics for the last 7 days including: session count, total injections, total tokens burned, per-layer breakdown (count, avg tokens, avg relevance), relevance distribution (strong >0.7, partial 0.3-0.7, filtered <0.3), citation rate, dedup hit rate, empty injection rate

#### Scenario: Custom time range
- **WHEN** `set-memory metrics --since 30d` is run
- **THEN** it SHALL display metrics for the last 30 days

#### Scenario: JSON output
- **WHEN** `set-memory metrics --json` is run
- **THEN** it SHALL output the same data as structured JSON (for programmatic consumption)

#### Scenario: No data available
- **WHEN** `set-memory metrics` is run and the database is empty or does not exist
- **THEN** it SHALL print "No metrics data. Enable with: set-memory metrics --enable" and exit 0

### Requirement: Top cited memories report
The TUI report SHALL include a "Top Cited Memories" section showing the most frequently cited memory content.

#### Scenario: Top 5 cited
- **WHEN** the report is generated with citation data available
- **THEN** it SHALL show up to 5 most-cited memory texts with their citation count, sorted descending

### Requirement: HTML dashboard command
The `set-memory dashboard` command SHALL generate a self-contained HTML file with interactive charts and open it in the default browser.

#### Scenario: Dashboard generation
- **WHEN** `set-memory dashboard` is run
- **THEN** it SHALL generate a single HTML file at `/tmp/set-memory-dashboard.html` with embedded Chart.js
- **AND** SHALL open it in the default browser (using `xdg-open` on Linux, `open` on macOS)

#### Scenario: Dashboard with time range
- **WHEN** `set-memory dashboard --since 30d` is run
- **THEN** the dashboard SHALL show data for the last 30 days

#### Scenario: Dashboard charts
- **WHEN** the dashboard is opened
- **THEN** it SHALL display: relevance score trend over time (line chart), token burn per day (bar chart), layer breakdown (pie/doughnut chart), citation rate over sessions (sparkline), session drill-down table with sortable columns

#### Scenario: Dashboard without data
- **WHEN** `set-memory dashboard` is run with no metrics data
- **THEN** it SHALL show an empty state message with instructions to enable metrics

### Requirement: Per-session drill-down
The HTML dashboard SHALL allow clicking on a session row to see detailed injection-level data for that session.

#### Scenario: Session detail view
- **WHEN** a user clicks a session row in the dashboard table
- **THEN** it SHALL expand to show all injections for that session with: timestamp, layer, query (truncated), result count, relevance scores, duration, token count

### Requirement: Dashboard self-contained
The HTML dashboard SHALL be a single file with no external dependencies (CSS, JS, fonts all inline or from CDN with fallback).

#### Scenario: Offline viewing
- **WHEN** the HTML file is opened without internet connection
- **THEN** the layout and data tables SHALL render correctly (charts MAY degrade if CDN is unavailable, but data SHALL still be visible in table format)
