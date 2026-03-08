## ADDED Requirements

### Requirement: get_current_tokens returns per-type breakdown
`get_current_tokens()` in `lib/loop/state.sh` SHALL return a JSON string containing `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_creation_tokens`, and `total_tokens` fields, parsed from `wt-usage --format json` output.

#### Scenario: Normal wt-usage available
- **WHEN** `wt-usage --format json` returns valid JSON with all token fields
- **THEN** `get_current_tokens()` returns a JSON string with all 5 fields extracted

#### Scenario: wt-usage unavailable
- **WHEN** `wt-usage` fails or is unavailable
- **THEN** `get_current_tokens()` returns `{"input_tokens":0,"output_tokens":0,"cache_read_tokens":0,"cache_creation_tokens":0,"total_tokens":0}`

### Requirement: Per-iteration token breakdown in loop-state
`add_iteration()` SHALL store `input_tokens`, `output_tokens`, `cache_read_tokens`, and `cache_create_tokens` alongside existing `tokens_used` in each iteration entry of loop-state.json.

#### Scenario: Iteration recorded with breakdown
- **WHEN** an iteration completes with token data available
- **THEN** the iteration entry in loop-state.json contains `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_create_tokens` fields in addition to `tokens_used`

#### Scenario: Estimation fallback
- **WHEN** `wt-usage` is unavailable and `estimate_tokens_from_files()` provides the total
- **THEN** per-type fields SHALL be 0 and `tokens_estimated` SHALL be true

### Requirement: Cumulative per-type totals in loop-state
`loop-state.json` SHALL maintain cumulative counters `total_input_tokens`, `total_output_tokens`, `total_cache_read`, and `total_cache_create` alongside existing `total_tokens`.

#### Scenario: Totals updated after iteration
- **WHEN** `update_loop_state` is called with the latest token snapshot
- **THEN** all 5 cumulative total fields are updated in loop-state.json

#### Scenario: New loop initialized
- **WHEN** `init_loop_state()` creates a fresh loop-state.json
- **THEN** all per-type total fields are initialized to 0

### Requirement: Engine computes per-type deltas
`lib/loop/engine.sh` SHALL compute before/after deltas for each token type individually using the JSON output from `get_current_tokens()`.

#### Scenario: Normal iteration delta
- **WHEN** `get_current_tokens()` returns JSON before and after claude runs
- **THEN** per-type deltas are computed as `type_after - type_before` for each of the 4 types
- **AND** negative deltas are clamped to 0

### Requirement: E2E report shows token breakdown
`bin/wt-e2e-report` SHALL display per-type token breakdown in both the Run Summary table and the Per-Change Results table.

#### Scenario: Run summary with breakdown
- **WHEN** the report is generated from orchestration-state.json
- **THEN** the Run Summary includes rows for Input, Output, Cache Read, and Cache Create in addition to Total Tokens

#### Scenario: Per-change table with breakdown
- **WHEN** per-change results are rendered
- **THEN** the table includes columns for In, Out, Cache R, Cache C alongside Total

#### Scenario: Missing breakdown data (backward compat)
- **WHEN** orchestration-state.json contains changes without per-type fields
- **THEN** the report shows 0 for missing type columns and still displays total correctly
