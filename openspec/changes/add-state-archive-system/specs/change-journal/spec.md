## ADDED Requirements

### Requirement: Centralized journaled fields list
The system SHALL maintain a single `_JOURNALED_FIELDS` frozenset in `lib/set_orch/state.py` that enumerates every state.json field whose overwrites are recorded to the change journal.

#### Scenario: Adding a field to the journal list
- **WHEN** a developer adds a new field name to the `_JOURNALED_FIELDS` frozenset
- **THEN** every subsequent call to `update_change_field()` for that field automatically journals without modifying any caller
- **THEN** no other code needs to be touched to enable journaling for the new field

#### Scenario: Initial field set
- **WHEN** the frozenset is initialized
- **THEN** it contains at minimum: `build_result`, `test_result`, `e2e_result`, `smoke_result`, `review_result`, `scope_check_result`, `rules_result`, `e2e_coverage_result`, `build_output`, `test_output`, `e2e_output`, `smoke_output`, `review_output`, `scope_check_output`, `rules_output`, `e2e_coverage_output`, `gate_build_ms`, `gate_test_ms`, `gate_e2e_ms`, `gate_review_ms`, `gate_smoke_ms`, `retry_context`, `status`, `current_step`

### Requirement: Journal append on field overwrite
The system SHALL append a JSONL entry to the change's journal file whenever `update_change_field()` changes a journaled field's value, without blocking the state update path.

#### Scenario: Journaled field value changes
- **WHEN** `update_change_field()` is called with a field in `_JOURNALED_FIELDS` and the new value differs from the old value
- **THEN** a JSONL line is appended to `<dirname(state_file)>/journals/<change-name>.jsonl` containing the timestamp, field name, old value, new value, and a monotonic sequence number
- **THEN** the append happens INSIDE the `locked_state` context manager, after the field mutation and alongside the existing `STATE_CHANGE` and `TOKENS` event emissions, so state update and journal append are atomic together
- **THEN** the path is derived purely from the `state_file` argument — no call to `SetRuntime()`, `resolve_project_name()`, or any subprocess, because `update_change_field()` is a hot path called hundreds of times per minute during active orchestration

#### Scenario: Journaled field value unchanged (no-op write)
- **WHEN** `update_change_field()` is called with a field in `_JOURNALED_FIELDS` but the new value equals the old value
- **THEN** no journal entry is appended
- **THEN** the state.json write still proceeds normally

#### Scenario: Non-journaled field update
- **WHEN** `update_change_field()` is called with a field NOT in `_JOURNALED_FIELDS`
- **THEN** no journal entry is appended
- **THEN** state.json is updated as before with no additional overhead beyond a single set membership check

#### Scenario: First write (no prior value)
- **WHEN** `update_change_field()` sets a journaled field for the first time (old value is `None`)
- **THEN** a journal entry IS appended with `old: null` and the new value
- **THEN** the entry establishes the baseline for subsequent history

### Requirement: Journal entry format
The system SHALL write journal entries in append-only JSONL format with a stable schema.

#### Scenario: Entry schema
- **WHEN** a journal entry is written
- **THEN** the JSON object contains exactly these keys: `ts` (ISO 8601 UTC), `field` (string), `old` (any JSON value including null), `new` (any JSON value), `seq` (integer)
- **THEN** the entry is terminated by a single newline
- **THEN** `seq` increases monotonically within each journal file, starting at 1

#### Scenario: Large field values
- **WHEN** a journaled field contains large output (e.g., an 8 KB e2e_output)
- **THEN** the full truncated-at-source value (as stored in state.json) is written to the journal without further truncation
- **THEN** binary or non-UTF8 data is sanitized to ensure valid JSON encoding

### Requirement: Non-blocking journal writes
The system SHALL NOT allow journal write failures to affect state correctness.

#### Scenario: Journal file not writable (permission denied)
- **WHEN** the journal directory cannot be created or the file cannot be opened for append
- **THEN** a WARNING is logged with the change name and field name
- **THEN** the state update is NOT rolled back; it remains committed
- **THEN** subsequent calls continue attempting to journal (no circuit breaker)

#### Scenario: Concurrent append from two processes
- **WHEN** two processes try to append to the same journal file simultaneously
- **THEN** only one process holds the state lock at a time, so journal appends for a single change are naturally serialized
- **THEN** both lines are preserved in order without truncation or interleaving

### Requirement: Journal API endpoint
The system SHALL expose a read endpoint that returns journal entries for a single change.

#### Scenario: Fetch journal for a change
- **WHEN** `GET /api/{project}/changes/{name}/journal` is called
- **THEN** the response contains an `entries` array with raw JSONL entries in chronological order
- **THEN** the response contains a `grouped` object keyed by gate name (build, test, e2e, review, smoke, …) whose value is an array of runs, each with `run` (1-indexed), `result`, `output`, `ts`, and `ms`
- **THEN** grouping logic pairs result/output/ms entries that share a timestamp and gate name

#### Scenario: Journal does not exist
- **WHEN** the endpoint is called for a change whose journal file is missing
- **THEN** the response returns `{"entries": [], "grouped": {}}` with HTTP 200
- **THEN** no error is raised

#### Scenario: Change not found
- **WHEN** the endpoint is called with a change name not present in state.json
- **THEN** the response returns HTTP 404 with an error message
