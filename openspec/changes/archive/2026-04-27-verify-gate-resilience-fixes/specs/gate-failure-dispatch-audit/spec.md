## ADDED Requirements

## IN SCOPE
- AST-level invariant: every gate-failure code path in `merger.py` and `verifier.py` either dispatches the agent (via `resume_change`) or emits a terminal-fail event.
- Regression test that detects new gate-failure paths violating the invariant.
- Opt-out marker (`# fail-dispatch-exempt` comment) for genuinely terminal paths.

## OUT OF SCOPE
- Refactoring the gate dispatch chain into a single façade.
- Runtime simulation of every gate failure mode (covered by integration tests, not this invariant).

### Requirement: Gate-failure paths must dispatch or terminate explicitly
Every code path in `lib/set_orch/merger.py` and `lib/set_orch/verifier.py` whose logical effect is "the gate failed" SHALL either:
- (a) Call `resume_change(state_file, change_name)` with a populated `retry_context`, OR
- (b) Emit `event_bus.emit("CHANGE_FAILED", change=name, data=...)` with a terminal-failure event type, OR
- (c) Be explicitly exempted with a `# fail-dispatch-exempt: <reason>` source comment on the same logical block.

Silent returns of `False` / fail-status without one of the above SHALL be detected as test-time errors.

#### Scenario: Test detects silent gate-failure path
- **WHEN** a developer adds a new function in `merger.py` that returns `False` after a test failure without calling `resume_change` or emitting `CHANGE_FAILED`
- **THEN** running `pytest tests/unit/test_gate_failure_dispatch.py` fails
- **AND** the failure message names the function and source line
- **AND** the message suggests the three valid resolutions (dispatch, terminal event, or exempt comment)

#### Scenario: Exempt comment suppresses the error
- **WHEN** a function in `verifier.py` legitimately returns fail-status as a terminal event for a guard condition (e.g., precondition check)
- **AND** the function carries `# fail-dispatch-exempt: precondition guard` comment
- **THEN** the regression test passes for that function

#### Scenario: subscription-management regression repro
- **WHEN** the regression test runs against `merger.py` at the commit before `db2e6a5c` (where integration-test fail returned False without dispatching)
- **THEN** the test fails and names the offending function
- **AND** the test passes at the post-fix commit

### Requirement: Scoped-subset spec-existence pre-validation
Before the e2e gate enters scoped-subset mode based on `retry_diff_files` output, the gate runner SHALL filter the candidate spec list against `Path.exists()` on each path. If 0 valid paths remain after filtering, the gate SHALL fall through to fallback mode (own-specs / full) WITHOUT entering subset mode at all.

#### Scenario: Bogus paths from retry_diff_files are filtered
- **WHEN** `retry_diff_files` returns `['tests/e2e/cookieconsentbanner.spec.ts', 'tests/e2e/product-card.spec.ts']` for a change
- **AND** neither file exists in the worktree
- **THEN** the gate runner does NOT log `Scoped gate: e2e running on 2 subset items: [bogus]`
- **AND** the gate falls through to fallback (full or own-specs scope)
- **AND** no subprocess is spawned for the empty subset

#### Scenario: Mixed valid/bogus paths keep only valid ones
- **WHEN** `retry_diff_files` returns 4 paths, 2 of which exist
- **THEN** the gate enters subset mode with only the 2 existing specs
- **AND** the log line accurately reports `Scoped gate: e2e running on 2 subset items: [<the valid 2>]`
