# Capability: verify-gate (delta)

## MODIFIED Requirements

### Requirement: VG-PIPELINE — Gate pipeline (handle_change_done)
Ordered steps: build → test → e2e → scope check → test file check → review → rules → verify → merge queue. Each gate step SHALL resolve a GateConfig via `resolve_gate_config()` at the start of the pipeline and use its `should_run()` and `is_blocking()` methods to determine execution. Gates with mode `"skip"` SHALL NOT execute and SHALL log "SKIPPED (gate_profile)". Gates with mode `"warn"` SHALL execute but failures SHALL NOT consume retry budget or block merge — they SHALL log a warning and continue. Gates with mode `"soft"` (spec_verify only) SHALL execute but failures SHALL be non-blocking if all other gates passed.

The E2E gate step SHALL pass the worktree path's Playwright configuration context to `_execute_e2e_gate()` so the gate can make webServer-aware decisions about health checks and port allocation.

The scope check step in the verify pipeline SHALL additionally call `profile.check_test_infra_usage(changed_files, project_path)` after existing scope checks. Any returned warning strings SHALL be logged at WARNING level with prefix `[TEST-INFRA]` and included in the scope check output. These warnings SHALL NOT be blocking — they SHALL NOT increment `verify_retry_count` and SHALL NOT prevent merge.

#### Scenario: Infrastructure change skips build/test/e2e
- **WHEN** a change with change_type `"infrastructure"` enters handle_change_done
- **THEN** the build, test, and e2e gate steps SHALL be skipped
- **AND** each SHALL log "Verify gate: <gate> SKIPPED for <name> (gate_profile)"
- **AND** scope_check, review, rules SHALL execute normally

#### Scenario: Feature change runs all gates
- **WHEN** a change with change_type `"feature"` enters handle_change_done
- **THEN** all gate steps SHALL execute with blocking behavior (identical to current behavior)

#### Scenario: E2E gate stores skip reason in extras
- **WHEN** the E2E gate returns a "skipped" result with an output message
- **THEN** the pipeline SHALL store the output in `change.extras["e2e_output"]`
- **AND** the skip reason SHALL be visible in the orchestration state

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

#### Scenario: Test infra advisory in scope check
- **WHEN** scope check runs and `check_test_infra_usage()` returns warnings
- **THEN** the warnings SHALL be logged as `[TEST-INFRA] <warning text>`
- **AND** the scope check SHALL still pass if no other blocking issues exist

#### Scenario: Profile without check_test_infra_usage
- **WHEN** scope check runs and the profile does not implement `check_test_infra_usage()`
- **THEN** no test infra warnings SHALL be emitted
- **AND** the scope check SHALL behave identically to current behavior
