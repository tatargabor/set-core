## MODIFIED Requirements

### Requirement: VG-PIPELINE — Gate pipeline (handle_change_done)
Ordered steps: build → test → e2e → scope check → test file check → review → rules → verify → merge queue. Each gate step SHALL resolve a GateConfig via `resolve_gate_config()` at the start of the pipeline and use its `should_run()` and `is_blocking()` methods to determine execution. Gates with mode `"skip"` SHALL NOT execute and SHALL log "SKIPPED (gate_profile)". Gates with mode `"warn"` SHALL execute but failures SHALL NOT consume retry budget or block merge — they SHALL log a warning and continue. Gates with mode `"soft"` (spec_verify only) SHALL execute but failures SHALL be non-blocking if all other gates passed.

The E2E gate step SHALL pass the worktree path's Playwright configuration context to `_execute_e2e_gate()` so the gate can make webServer-aware decisions about health checks and port allocation.

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
