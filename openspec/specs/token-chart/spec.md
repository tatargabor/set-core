## ADDED Requirements

### Requirement: Token consumption time-series chart
Display a Recharts line chart showing token usage over time.

#### Scenario: Chart in dashboard
- **WHEN** the dashboard has token event data
- **THEN** a chart area shows token consumption over time (line or area chart)
- **THEN** X-axis is time, Y-axis is cumulative tokens
- **THEN** separate lines for input and output tokens

#### Scenario: Per-change token breakdown
- **WHEN** hovering over the chart
- **THEN** a tooltip shows which change was consuming tokens at that point

#### Scenario: Chart data source
- **WHEN** rendering the chart
- **THEN** data comes from `orchestration-state-events.jsonl` TOKENS events
- **THEN** events contain timestamp and cumulative token counts

### Requirement: Events API endpoint

#### Scenario: Get token events
- **WHEN** `GET /api/{project}/events?type=TOKENS` is called
- **THEN** returns filtered events from the JSONL file as a JSON array
- **THEN** supports pagination or limit parameter for large files
