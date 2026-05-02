## ADDED Requirements

### Requirement: Per-gate failure reason shall be surfaced in journal/changes API
The journal/changes API responses SHALL include, on each per-gate entry, optional fields naming the cause of failure: `terminal_reason` (string copied from `GateResult.terminal_reason`), `verdict_source` (string copied from the corresponding `<session_id>.verdict.json` sidecar's `source` field), and `verdict_summary` (string copied from the sidecar's `summary` field). These fields SHALL be omitted when the underlying data is absent. The fields SHALL never be the literal string `"unknown"` — absence is signalled by the field being missing, not by a placeholder value.

#### Scenario: Verifier gate timeout surfaces terminal_reason
- **GIVEN** the `spec_verify` gate failed with `terminal_reason="timeout"` in the orchestrator state
- **WHEN** the journal/changes API is queried for the change
- **THEN** the per-gate entry for `spec_verify` SHALL include `"terminal_reason": "timeout"`

#### Scenario: Review gate verdict source surfaces from sidecar
- **GIVEN** the `review` gate produced a `<session_id>.verdict.json` sidecar with `source="classifier_confirmed"` and `summary="0 critical findings"`
- **WHEN** the journal/changes API is queried
- **THEN** the per-gate entry for `review` SHALL include `"verdict_source": "classifier_confirmed"` and `"verdict_summary": "0 critical findings"`

#### Scenario: Pre-fix data omits the new fields
- **GIVEN** a change run before the verdict-sidecar feature shipped (no `terminal_reason`, no sidecar)
- **WHEN** the journal/changes API is queried
- **THEN** the per-gate entry SHALL omit `terminal_reason`, `verdict_source`, and `verdict_summary`
- **AND** SHALL NOT contain placeholder values like `"unknown"` or `null` for those fields

### Requirement: Sidecar lookup failures shall not break responses
When the verdict-sidecar file is corrupt or unreadable, the API response SHALL still return the gate's `result` and other fields, omitting only the verdict-sourced fields. A WARNING SHALL be logged identifying the unreadable sidecar path.

#### Scenario: Corrupt sidecar logged but ignored
- **GIVEN** a change whose `review.verdict.json` sidecar contains malformed JSON
- **WHEN** the journal/changes API is queried
- **THEN** the response SHALL succeed with the `review` entry's `result` populated and `verdict_source`/`verdict_summary` omitted
- **AND** a WARNING SHALL be logged naming the corrupt sidecar path
