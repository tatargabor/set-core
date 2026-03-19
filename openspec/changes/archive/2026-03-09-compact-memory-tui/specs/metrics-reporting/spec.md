## MODIFIED Requirements

### Requirement: TUI metrics report command
The `set-memory metrics` command SHALL read the SQLite database and print a formatted text report to stdout, including usage rate from passive transcript matching.

#### Scenario: Default report (last 7 days)
- **WHEN** `set-memory metrics` is run without arguments
- **THEN** it SHALL display metrics for the last 7 days including: session count, total injections, total tokens burned, per-layer breakdown (count, avg tokens, avg relevance), relevance distribution (strong >0.7, partial 0.3-0.7, filtered <0.3), usage rate (passively matched/injected), legacy citation rate, dedup hit rate, empty injection rate

#### Scenario: Project-filtered report
- **WHEN** `set-memory metrics --project sales-raketa` is run
- **THEN** it SHALL display metrics filtered to sessions whose project name starts with `sales-raketa`

#### Scenario: Custom time range
- **WHEN** `set-memory metrics --since 30d` is run
- **THEN** it SHALL display metrics for the last 30 days

#### Scenario: JSON output
- **WHEN** `set-memory metrics --json` is run
- **THEN** it SHALL output the same data as structured JSON including `usage_rate`, `total_injected_ids`, `total_matched_ids` fields

#### Scenario: No data available
- **WHEN** `set-memory metrics` is run and the database is empty or does not exist
- **THEN** it SHALL print "No metrics data. Enable with: set-memory metrics --enable" and exit 0

## ADDED Requirements

### Requirement: Project filter parameter in query_report
The `query_report()` function SHALL accept an optional `project` parameter for filtering.

#### Scenario: Query with project filter
- **WHEN** `query_report(project="sales-raketa")` is called
- **THEN** all SQL queries SHALL include `WHERE sessions.project LIKE 'sales-raketa%'` in addition to the date cutoff

#### Scenario: Query without project filter
- **WHEN** `query_report()` is called without a project parameter
- **THEN** it SHALL return globally aggregated metrics as current behavior (backward compatible)

#### Scenario: Project filter with no matching sessions
- **WHEN** `query_report(project="nonexistent")` is called
- **THEN** it SHALL return `None`
