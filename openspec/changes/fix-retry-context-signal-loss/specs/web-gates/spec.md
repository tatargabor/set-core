## ADDED Requirements

### Requirement: E2E gate retry_context preserves error-tail evidence

The web module's E2E gate (`execute_e2e_gate` in `modules/web/set_project_web/gates.py`) SHALL construct `retry_context` such that Playwright assertion errors, stack traces, and failure reason messages — which conventionally appear near the end of stdout — are preserved when the output exceeds the budget.

The gate SHALL NOT use a head-only slice (e.g., `e2e_output[:N]`) to truncate the output embedded in retry_context. It SHALL use `smart_truncate_structured` from `lib/set_orch/truncate.py` (or an equivalent utility providing head + tail preservation with error-line extraction from the middle).

The truncation budget SHALL be at least 6000 characters for the E2E output section of retry_context, chosen so that after the failing-test header (up to ~1500 chars for large failure sets) there remains a meaningful head and tail from the raw Playwright output. The budget MAY be smaller in proportion to the actual output length when the output is small.

#### Scenario: Playwright output with assertion errors at the tail

- **GIVEN** `e2e_output` is 32000 chars long and contains prisma setup noise in the first 10 000 chars, the per-test registration list in the middle, and Playwright assertion error messages with stack traces in the last 5 000 chars
- **AND** two tests fail with distinct assertion error messages
- **WHEN** `execute_e2e_gate` builds `retry_context`
- **THEN** the retry_context SHALL include text that contains at least one of the assertion error messages OR error-marker lines (e.g., `Error:`, `expected`, `Timeout`, `FAIL`) preserved from the tail or middle
- **AND** the retry_context SHALL NOT end abruptly mid-sentence inside prisma generate output (e.g., not end with `"Running generate... ["`)
- **AND** the retry_context SHALL include the list of failing test files/lines (existing header behavior preserved)

#### Scenario: Output within budget is passed through unchanged

- **GIVEN** `e2e_output` is 3000 chars long and the truncation budget is 6000
- **WHEN** `execute_e2e_gate` builds `retry_context`
- **THEN** the full `e2e_output` SHALL appear in retry_context without a truncation marker

#### Scenario: Failing-test header is preserved regardless of truncation

- **GIVEN** 33 tests fail and the failing-test header consumes ~1500 chars
- **WHEN** `execute_e2e_gate` builds `retry_context`
- **THEN** the `"E2E: N NEW failures"` header and the full `"New failures: <comma-separated list>"` SHALL appear verbatim in retry_context before the truncated output section

### Requirement: Default web template enables the unit test gate

The `modules/web/set_project_web/templates/nextjs/set/orchestration/config.yaml` file — copied verbatim into newly initialized consumer projects by `set-project init` — SHALL ship with `test_command: pnpm test` uncommented (active). The template MAY include a comment line clarifying that the unit test gate is a no-op (skipped) when no test files are present in the consumer project.

This default applies only to newly initialized projects. Existing consumer projects are not automatically re-initialized and retain whatever `test_command` value they have.

#### Scenario: Fresh consumer project has active test_command

- **GIVEN** a developer runs `set-project init --project-type web --template nextjs` against a clean repository
- **WHEN** the generated `set/orchestration/config.yaml` is read
- **THEN** the file SHALL contain an active (uncommented) `test_command:` entry with a value of `pnpm test`

#### Scenario: Unit test gate is a no-op when no tests exist

- **GIVEN** the consumer project's `package.json` has a `"test"` script that exits non-zero with "no tests found" (or similar) when no test files exist
- **AND** `test_command` is set to `pnpm test`
- **WHEN** a change is run and no vitest/jest files exist in the worktree
- **THEN** the test gate SHALL classify the outcome as `skipped` rather than `fail` — per the existing test-gate skipped-on-no-tests handling
- **AND** the gate SHALL NOT block the verify pipeline
