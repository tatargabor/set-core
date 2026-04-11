## MODIFIED Requirements

### Requirement: Worktree E2E gate never returns PASS on incomplete runs
The `execute_e2e_gate` function in `modules/web/set_project_web/gates.py` SHALL distinguish timeouts and unparseable failures from real test failures. When the underlying `run_command` reports `timed_out = True`, OR when `exit_code != 0` combined with an empty failure-ID extraction, the gate SHALL return `GateResult(status="fail", ...)`. The baseline comparison branch SHALL only execute when at least one parseable failure ID exists.

#### Scenario: Timed-out run returns fail
- **GIVEN** `run_command` returns `CommandResult(exit_code=-1, timed_out=True, stdout=<mid-run progress without summary>, stderr="")`
- **WHEN** `execute_e2e_gate` is called with a valid worktree and Playwright config
- **THEN** the returned `GateResult` SHALL have `status == "fail"`
- **AND** the `output` SHALL contain the phrase "timed out" and the timeout value
- **AND** the `retry_context` SHALL explain this is an infrastructure signal (not an assertion failure)
- **AND** the baseline comparison SHALL NOT execute

#### Scenario: Non-zero exit with no parseable failure list returns fail
- **GIVEN** `run_command` returns `CommandResult(exit_code=2, timed_out=False, stdout=<crash trace, no numbered failure list>, stderr="")`
- **AND** `_extract_e2e_failure_ids(stdout)` returns an empty set
- **WHEN** `execute_e2e_gate` is called
- **THEN** the returned `GateResult` SHALL have `status == "fail"`
- **AND** the `output` SHALL mention the exit code and "no parseable failure list"
- **AND** the `retry_context` SHALL hint at crash / OOM / formatter drift
- **AND** the baseline comparison SHALL NOT execute

#### Scenario: Real failure with parseable list enters baseline comparison
- **GIVEN** `run_command` returns `CommandResult(exit_code=1, timed_out=False, stdout=<Playwright output with "1) [chromium] › foo.spec.ts:45" line>, stderr="")`
- **AND** `_extract_e2e_failure_ids(stdout)` returns a non-empty set
- **WHEN** `execute_e2e_gate` is called
- **THEN** baseline comparison SHALL execute (the existing logic)
- **AND** if there are no new failures vs baseline, the gate returns `"pass"`
- **AND** if there are new failures, the gate returns `"fail"` with the new-failures list in the header

### Requirement: Default e2e_timeout covers realistic web-suite runtime
Both `Directives.e2e_timeout` in `lib/set_orch/engine.py` and `DEFAULT_E2E_TIMEOUT` in `lib/set_orch/verifier.py` SHALL default to `300` seconds. This is measurement-backed: a 100+ test Playwright suite with Prisma seeding and Next.js dev server cold-start takes ~150s on commodity hardware; 300s provides ~2x headroom.

#### Scenario: New run without explicit e2e_timeout uses 300s
- **WHEN** a `Directives` instance is constructed without an explicit `e2e_timeout`
- **THEN** the field value SHALL equal 300
- **AND** the same default SHALL be used by the verifier pipeline's `DEFAULT_E2E_TIMEOUT` constant

#### Scenario: Explicit directive override still honored
- **GIVEN** an orchestration config specifying `e2e_timeout: 180`
- **WHEN** directives are parsed
- **THEN** the resulting `Directives.e2e_timeout == 180` (override wins)
- **AND** the new timeout guard clause still fires if the 180s budget is hit

### Requirement: E2E capture is large; storage is pattern-preserving truncated
The `run_command` calls inside `execute_e2e_gate` (both the worktree-stage run and the baseline-regeneration run inside `_get_or_create_e2e_baseline`) SHALL pass `max_output_size=_E2E_CAPTURE_MAX_BYTES` where `_E2E_CAPTURE_MAX_BYTES` is a module-level constant set to `4 * 1024 * 1024` (4 MiB). This ceiling SHALL be large enough to cover extreme failure counts (200+ failures with full stack traces or multi-KB JSON assertion diffs) so that `_extract_e2e_failure_ids` sees every failure entry in the suite. The final `GateResult.output` SHALL contain the full captured output (no downstream head-slicing).

When the gate result is persisted into state (via `gate_runner.py`), the e2e output SHALL be truncated to 32000 bytes using `smart_truncate_structured` with a Playwright-aware keep pattern that matches numbered failure entries (`\d+\)\s+\[.*?\]\s+[›»]\s+[^\s:]+\.spec\.\w+`), so that the numbered failure list is preserved across the truncation boundary.

#### Scenario: Large failure list is captured and extracted fully
- **GIVEN** a Playwright run that emits 2MB of output including a 200-failure numbered list with long assertion diffs
- **WHEN** `execute_e2e_gate` runs the worktree-stage e2e command
- **THEN** `run_command` returns the full output (up to the 4 MiB capture ceiling)
- **AND** `_extract_e2e_failure_ids` on that output returns all 200 failure IDs
- **AND** the baseline comparison correctly classifies each failure

#### Scenario: Storage truncation preserves failure lines
- **GIVEN** a `GateResult` whose `output` field contains 200KB of Playwright output including the 50-failure list
- **WHEN** the gate runner persists it via `update_change_field` (or `commit_results`)
- **THEN** the persisted `e2e_output` field in the state file is at most ~32000 characters
- **AND** the persisted output contains all 50 numbered failure lines (preserved by the keep pattern)
- **AND** the persisted output contains both the first and last portions of the original (head + tail)

#### Scenario: Non-e2e gates retain the narrow budget
- **GIVEN** a `GateResult` for the `build` or `test` gate with a 50KB output
- **WHEN** the gate runner persists it
- **THEN** the persisted output is truncated to 2000 characters (not 32000)
- **AND** the existing `smart_truncate` behavior for non-e2e gates is unchanged
