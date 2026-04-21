## ADDED Requirements

### Requirement: Per-change token-runaway circuit breaker
The engine SHALL monitor per-change cumulative `input_tokens` growth between successive `VERIFY_GATE` events with the same `stop_gate` + `finding_fingerprint`. When the delta exceeds `token_runaway_threshold` (default 20,000,000 tokens, configurable via directive `per_change_token_runaway_threshold`), the engine SHALL:

1. Pause the change by setting `status=failed:token_runaway`
2. Emit a `TOKEN_RUNAWAY` event with `{change, baseline_tokens, current_tokens, delta, stop_gate, finding_fingerprint}`
3. Surface the change to the investigation/fix-iss pipeline (same hook as `stuck-loop` escalation)

Observed on `craftbrew-run-20260418-1719::promotions-engine`: `input_tokens` grew from ~70.5M to ~71.1M across a single stuck-loop iteration; left unchecked across 23 iterations the figure would have grown without bound while the gate state never changed.

#### Scenario: Baseline captured at first gate run
- **WHEN** the verify pipeline runs a `VERIFY_GATE` for the first time on a change
- **THEN** `token_runaway_baseline` SHALL be set to the current `input_tokens` for that change
- **AND** the `(stop_gate, finding_fingerprint)` of that gate result SHALL be recorded

#### Scenario: Delta stays below threshold
- **WHEN** the next gate run shows the same `stop_gate` + `finding_fingerprint` and `current - baseline < 20M`
- **THEN** no circuit-breaker action SHALL be taken

#### Scenario: Delta exceeds threshold triggers circuit breaker
- **WHEN** the next gate run shows the same fingerprint and `current - baseline ≥ 20M`
- **THEN** the engine SHALL write `change.status = 'failed:token_runaway'`
- **AND** emit a `TOKEN_RUNAWAY` event
- **AND** trigger investigation/fix-iss

#### Scenario: Baseline resets on gate-state change
- **WHEN** the gate result's `stop_gate` OR `finding_fingerprint` changes
- **THEN** `token_runaway_baseline` SHALL be updated to the new `input_tokens`
- **AND** the recorded fingerprint SHALL be updated

### Requirement: State schema carries runaway fields
`orchestration-state.json`'s per-change dict SHALL gain two fields: `token_runaway_baseline: int | None` and `last_gate_fingerprint: str | None`. Both SHALL default to `None` and be backwards-compatible with states lacking them.

**Ownership of `last_gate_fingerprint`**: this field is written **only** by the verifier at the end of each verify-pipeline run, carrying the `(stop_gate, sorted(finding_fingerprints))` tuple serialised as a stable string. Both the token-runaway circuit breaker (this spec) and the stuck-loop counter (see `retry-loop-completion` spec delta) are **readers** of this field — neither writes it. This avoids a race between two writers.

#### Scenario: Verifier writes last_gate_fingerprint after gate completion
- **WHEN** the verify pipeline finishes a gate run for a change
- **THEN** the verifier SHALL serialise `(stop_gate, sorted(finding_fingerprints))` as a stable string and write it to `change.last_gate_fingerprint`
- **AND** the write SHALL happen in the same state transaction as the `VERIFY_GATE` event emission

#### Scenario: Old state file loads without runaway fields
- **WHEN** an `orchestration-state.json` without `token_runaway_baseline` is loaded
- **THEN** the loader SHALL populate the field as `None` on each change
- **AND** the first gate run SHALL set the baseline (initial capture, above)
