## MODIFIED Requirements

### Requirement: VG-PIPELINE — Gate pipeline (handle_change_done)
Ordered steps: build → test → e2e → scope check → test file check → review → rules → verify → merge queue. Each gate step SHALL resolve a GateConfig via `resolve_gate_config()` at the start of the pipeline and use its `should_run()` and `is_blocking()` methods to determine execution. Gates with mode `"skip"` SHALL NOT execute and SHALL log "SKIPPED (gate_profile)". Gates with mode `"warn"` SHALL execute but failures SHALL NOT consume retry budget or block merge — they SHALL log a warning and continue. Gates with mode `"soft"` (spec_verify only) SHALL execute but failures SHALL be non-blocking if all other gates passed.

#### Scenario: Infrastructure change skips build/test/e2e
- **WHEN** a change with change_type `"infrastructure"` enters handle_change_done
- **THEN** the build, test, and e2e gate steps SHALL be skipped
- **AND** each SHALL log "Verify gate: <gate> SKIPPED for <name> (gate_profile)"
- **AND** scope_check, review, rules SHALL execute normally

#### Scenario: Feature change runs all gates
- **WHEN** a change with change_type `"feature"` enters handle_change_done
- **THEN** all gate steps SHALL execute with blocking behavior (identical to current behavior)

#### Scenario: Warn-mode test failure is non-blocking
- **WHEN** a schema change runs tests (gate mode `"warn"`) and tests fail
- **THEN** the failure SHALL be logged as a warning
- **AND** the verify_retry_count SHALL NOT be incremented
- **AND** the pipeline SHALL continue to the next gate
- **AND** test_result SHALL be set to `"warn-fail"`

#### Scenario: Effective max_retries from GateConfig
- **WHEN** GateConfig has `max_retries` set to a non-None value
- **THEN** the verifier SHALL use that value instead of the global `max_verify_retries` parameter for all blocking gates in this change

#### Scenario: Review model override from GateConfig
- **WHEN** GateConfig has `review_model` set to a non-None value
- **THEN** the review gate SHALL use that model instead of the global `review_model` parameter
