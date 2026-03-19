## ADDED Requirements

### Requirement: Unified TUI command
The `set-memory tui` command SHALL display a unified dashboard combining memory DB statistics, hook overhead metrics, and usage signals.

#### Scenario: Default invocation
- **WHEN** `set-memory tui` is run without arguments
- **THEN** it SHALL display a formatted report covering the last 7 days of metrics data

#### Scenario: Custom time range
- **WHEN** `set-memory tui --since 30d` is run
- **THEN** it SHALL display metrics covering the last 30 days

#### Scenario: JSON output
- **WHEN** `set-memory tui --json` is run
- **THEN** it SHALL output the full dashboard data as structured JSON

### Requirement: Memory DB stats section
The TUI SHALL display a "Memory Database" section showing current state of the memory store.

#### Scenario: Memory DB overview
- **WHEN** the TUI renders the Memory Database section
- **THEN** it SHALL show: total memory count, type distribution (Learning/Context/Decision counts), noise ratio (% with importance < 0.3), top 5 tags by frequency

#### Scenario: Memory DB unavailable
- **WHEN** `set-memory stats` fails or returns no data
- **THEN** the section SHALL show "Memory DB: unavailable" and continue rendering other sections

### Requirement: Hook overhead section
The TUI SHALL display a "Hook Overhead" section showing injection metrics per layer.

#### Scenario: Per-layer breakdown
- **WHEN** the TUI renders the Hook Overhead section
- **THEN** it SHALL show for each layer (L1-L4): injection count, average tokens per injection, average relevance score, dedup hit count, average duration in milliseconds

#### Scenario: Token budget estimate
- **WHEN** the TUI renders the Hook Overhead section
- **THEN** it SHALL show: total tokens injected across all sessions, average tokens per session, estimated percentage of session token budget (using 200K as denominator)

### Requirement: Usage signals section
The TUI SHALL display a "Usage Signals" section showing how effectively memories are being used.

#### Scenario: Usage rate display
- **WHEN** the TUI renders the Usage Signals section with context_id data available
- **THEN** it SHALL show: usage rate (cited/injected as percentage), total IDs injected, total IDs cited, comparison to old citation rate (string-match based)

#### Scenario: No context_id data yet
- **WHEN** the TUI renders and no context_id injection data exists (pre-upgrade sessions)
- **THEN** the usage rate line SHALL show "N/A (context_id tracking not yet active)" and fall back to showing legacy citation rate only

#### Scenario: Relevance distribution
- **WHEN** the TUI renders the Usage Signals section
- **THEN** it SHALL show a histogram of relevance scores: strong (>0.7), partial (0.3-0.7), weak (<0.3) with counts and ASCII bar chart

#### Scenario: Empty injection rate
- **WHEN** the TUI renders the Usage Signals section
- **THEN** it SHALL show the percentage of non-dedup injections that returned zero results

### Requirement: Daily trend section
The TUI SHALL display a "Daily Trend" section showing token burn and relevance over time.

#### Scenario: Sparkline rendering
- **WHEN** the TUI renders daily trend data for 7+ days
- **THEN** it SHALL show ASCII sparklines (using block characters ▁▂▃▄▅▆▇█) for: daily token burn, daily average relevance, daily usage rate (when available)

#### Scenario: Fewer than 3 days of data
- **WHEN** fewer than 3 days of data exist
- **THEN** the trend section SHALL show raw numbers per day instead of sparklines
