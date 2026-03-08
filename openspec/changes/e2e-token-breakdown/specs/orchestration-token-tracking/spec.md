## ADDED Requirements

### Requirement: Per-type token fields in orchestration state
Each change entry in `orchestration-state.json` SHALL include `input_tokens`, `output_tokens`, `cache_read_tokens`, and `cache_create_tokens` fields alongside existing `tokens_used`.

#### Scenario: Change initialized with per-type fields
- **WHEN** a new change is added to orchestration-state.json
- **THEN** the change entry includes `input_tokens: 0`, `output_tokens: 0`, `cache_read_tokens: 0`, `cache_create_tokens: 0`

#### Scenario: Backward compatible with existing state files
- **WHEN** an orchestration-state.json without per-type fields is loaded
- **THEN** missing fields default to 0 and do not cause errors

### Requirement: Verifier syncs per-type tokens
The verifier SHALL sync all 4 per-type token fields from loop-state.json to orchestration-state.json, respecting `tokens_used_prev` accumulation for retries.

#### Scenario: Normal token sync
- **WHEN** the verifier reads loop-state.json with per-type totals
- **THEN** it updates the corresponding change's `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_create_tokens` in orchestration-state.json

#### Scenario: Retry accumulation
- **WHEN** a change is retried and has `tokens_used_prev` from a previous attempt
- **THEN** per-type token fields accumulate across retries (previous + current)

### Requirement: Total tokens in orchestration summary
The orchestration status display SHALL show per-type token totals in addition to aggregate total.

#### Scenario: Status display includes breakdown
- **WHEN** orchestration status is printed
- **THEN** total input, output, cache_read, and cache_create are shown alongside total tokens
