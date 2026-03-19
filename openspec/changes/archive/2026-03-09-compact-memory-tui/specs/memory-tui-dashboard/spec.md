## MODIFIED Requirements

### Requirement: Unified TUI command
The `set-memory tui` command SHALL display a unified dashboard combining memory DB statistics, hook overhead metrics, and usage signals, scoped to the current project.

#### Scenario: Default invocation from project directory
- **WHEN** `set-memory tui` is run from a git project directory without arguments
- **THEN** it SHALL display a project-scoped formatted report covering the last 7 days of metrics data in 3-column layout

#### Scenario: Custom time range
- **WHEN** `set-memory tui --since 30d` is run
- **THEN** it SHALL display metrics covering the last 30 days

#### Scenario: JSON output
- **WHEN** `set-memory tui --json` is run
- **THEN** it SHALL output the full dashboard data as structured JSON including the project filter applied

### Requirement: Memory DB stats section
The TUI left column SHALL display a "Memory Database" section showing current state of the memory store.

#### Scenario: Memory DB overview
- **WHEN** the TUI renders the Memory Database section
- **THEN** it SHALL show: total memory count, type distribution (Learning/Context/Decision counts), noise ratio (% with importance < 0.3), top 5 tags by frequency

#### Scenario: Memory DB unavailable
- **WHEN** `set-memory stats` fails or returns no data
- **THEN** the section SHALL show "Memory DB: unavailable" and continue rendering other sections

### Requirement: Hook overhead section
The TUI center column SHALL display a "Hook Overhead" section showing injection metrics per layer.

#### Scenario: Per-layer breakdown
- **WHEN** the TUI renders the Hook Overhead section
- **THEN** it SHALL show for each layer (L1-L4): injection count, average tokens per injection, average relevance score

#### Scenario: Token budget estimate
- **WHEN** the TUI renders the Hook Overhead section
- **THEN** it SHALL show: total tokens injected across all sessions, average tokens per session, estimated percentage of session token budget (using 200K as denominator)

### Requirement: Usage signals section
The TUI left column SHALL display a "Usage Signals" section below the Memory Database section.

#### Scenario: Usage rate display
- **WHEN** the TUI renders the Usage Signals section with context_id data available
- **THEN** it SHALL show: usage rate (cited/injected as percentage), total IDs injected, total IDs cited

#### Scenario: No context_id data yet
- **WHEN** the TUI renders and no context_id injection data exists
- **THEN** the usage rate line SHALL show "N/A"

#### Scenario: Relevance distribution
- **WHEN** the TUI renders the Usage Signals section
- **THEN** it SHALL show a histogram of relevance scores: strong (>0.7), partial (0.3-0.7), weak (<0.3) with ASCII bar chart

### Requirement: Daily trend section
The TUI center column SHALL display a "Daily Trend" section showing token burn and relevance sparklines.

#### Scenario: Sparkline rendering
- **WHEN** the TUI has >= 3 days of data
- **THEN** it SHALL show sparkline graphs for daily token burn and daily average relevance with min/max range labels
