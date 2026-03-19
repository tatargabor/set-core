## ADDED Requirements

## IN SCOPE
- GatePipeline class that orchestrates sequential gate execution with unified retry/fail/skip logic
- GateResult dataclass capturing per-gate outcome, duration, and output
- Batch state update — single locked write for all gate results instead of per-field calls
- Review extra retry configurable via GateConfig (currently hardcoded +1)
- Screenshot collection unified into a single helper

## OUT OF SCOPE
- Changing gate execution order (build → test → e2e → scope → test_files → review → rules → spec_verify remains)
- Adding new gate types
- Changing the retry prompt content or review feedback format
- Modifying the smoke pipeline (post-merge, stays in merger.py)

### Requirement: GatePipeline orchestrates gate execution
The system SHALL provide a `GatePipeline` class in `lib/wt_orch/gate_runner.py` that accepts a `GateConfig`, state file path, change name, and execution parameters. The pipeline SHALL execute gates in sequence, collecting `GateResult` objects. Each gate SHALL be invoked via a callable (`GateExecutor`) that returns a `GateResult`.

#### Scenario: Pipeline executes gates in order
- **WHEN** `GatePipeline.run()` is called with registered gate executors
- **THEN** gates SHALL execute in registration order
- **AND** each gate's result SHALL be appended to `pipeline.results`

#### Scenario: Skipped gate produces skip result
- **WHEN** a gate's `GateConfig.should_run(name)` returns `False`
- **THEN** the pipeline SHALL NOT call the gate executor
- **AND** SHALL append a `GateResult` with `status="skipped"` and `duration_ms=0`

#### Scenario: Non-blocking failure continues pipeline
- **WHEN** a gate executor returns `GateResult(status="fail")`
- **AND** `GateConfig.is_blocking(name)` returns `False`
- **THEN** the pipeline SHALL set the result status to `"warn-fail"`
- **AND** SHALL continue to the next gate
- **AND** SHALL NOT increment `verify_retry_count`

#### Scenario: Blocking failure triggers retry or fail
- **WHEN** a gate executor returns `GateResult(status="fail")`
- **AND** `GateConfig.is_blocking(name)` returns `True`
- **THEN** the pipeline SHALL check `verify_retry_count < max_retries`
- **AND** if retries available: increment counter, set status to `"verify-failed"`, store retry context, call `resume_change`, and stop the pipeline
- **AND** if retries exhausted: set status to `"failed"`, send notification, and stop the pipeline

### Requirement: GateResult captures gate outcome
The system SHALL define a `GateResult` dataclass with fields: `gate_name: str`, `status: str` (one of `"pass"`, `"fail"`, `"warn-fail"`, `"skipped"`), `output: str`, `duration_ms: int`, and optional `stats: dict`.

#### Scenario: GateResult records timing
- **WHEN** a gate executor runs for 1500ms and passes
- **THEN** the GateResult SHALL have `status="pass"` and `duration_ms=1500`

### Requirement: Batch state update after pipeline completion
The pipeline SHALL commit all gate results to state in a single `locked_state` block instead of individual `update_change_field` calls per result.

#### Scenario: All results written atomically
- **WHEN** the pipeline completes (all gates pass)
- **THEN** a single `locked_state` call SHALL write all gate results, timings, and the final status
- **AND** individual `update_change_field` calls SHALL NOT be used for gate results within the pipeline

#### Scenario: Early exit still writes partial results
- **WHEN** the pipeline stops early due to a blocking failure
- **THEN** all results collected so far (including the failing gate) SHALL be written in a single batch

### Requirement: Review extra retry configurable
The `GateConfig` dataclass SHALL include a `review_extra_retries: int` field (default `1`). The review gate retry limit SHALL be `max_retries + review_extra_retries` instead of the hardcoded `+1`.

#### Scenario: Default review extra retry is 1
- **WHEN** a GateConfig is created with defaults
- **THEN** `review_extra_retries` SHALL be `1`

#### Scenario: Custom review extra retry
- **WHEN** GateConfig has `review_extra_retries=0`
- **THEN** the review gate SHALL have the same retry limit as other gates

### Requirement: Unified screenshot collection
The system SHALL provide a single `collect_screenshots(change_name, source_dir, category)` function that handles both smoke and e2e screenshot collection with consistent path resolution via `WtRuntime`.

#### Scenario: Smoke screenshots collected consistently
- **WHEN** smoke tests produce screenshots in `test-results/`
- **THEN** `collect_screenshots(name, "test-results", "smoke")` SHALL copy them to the WtRuntime smoke screenshots directory with attempt numbering

#### Scenario: E2E screenshots collected consistently
- **WHEN** e2e tests produce screenshots in a worktree's `test-results/`
- **THEN** `collect_screenshots(name, wt_test_results, "e2e")` SHALL copy them to the WtRuntime e2e screenshots directory
