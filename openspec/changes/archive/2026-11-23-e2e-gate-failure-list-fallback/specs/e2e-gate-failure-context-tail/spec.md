## IN SCOPE
- Inline tail of `e2e_output` (stdout/stderr) into the gate's `retry_context` when Playwright crashes before emitting a parseable failure list
- Crash-marker line extraction (`Error:`, `Traceback`, `webServer`, `Killed`, `OOM`, `assert`) preserved separately so they survive any tail truncation
- Cap on inlined lines to prevent context bloat (default 80, configurable via `gate_overrides.e2e.failure_tail_lines`)

## OUT OF SCOPE
- Modifying the parseable-failure-list path (when Playwright DID emit per-test failure lines, the existing logic stands)
- Changing the gate's classification logic
- Adding new gates or new retry semantics
- Tail extraction for other gates (build/test/smoke produce their own context already)

## ADDED Requirements

### Requirement: Unparseable-failure retry_context includes a stdout/stderr tail

When the E2E gate's `_extract_e2e_failure_ids(e2e_output)` returns empty AND `e2e_cmd_result.exit_code != 0`, the gate SHALL append a `## Stdout/stderr tail (last N lines)` section to the produced `retry_context`. The section SHALL contain the trailing N lines of `e2e_output` verbatim, where N defaults to 80 and SHALL be overridable via `gate_overrides.e2e.failure_tail_lines`.

#### Scenario: Crash with empty failure list — tail included

- **GIVEN** the e2e command exits with code 1
- **AND** `_extract_e2e_failure_ids` returns `[]` (no parseable Playwright per-test failures)
- **AND** the trailing 200 lines of `e2e_output` contain a stack trace
- **WHEN** the gate produces `retry_context`
- **THEN** the `retry_context` SHALL contain a `## Stdout/stderr tail (last 80 lines)` heading
- **AND** SHALL contain the last 80 lines of `e2e_output` verbatim under that heading

#### Scenario: Short output included whole

- **GIVEN** `e2e_output` is shorter than 80 lines
- **WHEN** the gate produces `retry_context`
- **THEN** the entire `e2e_output` SHALL appear under the tail heading
- **AND** the heading SHALL read `## Stdout/stderr tail (last <N> lines)` where `<N>` is the actual line count

#### Scenario: Override via gate_overrides

- **GIVEN** `gate_overrides.e2e.failure_tail_lines: 200` is set in the project's directives
- **WHEN** the gate produces `retry_context` for an unparseable failure
- **THEN** the tail SHALL contain up to 200 lines (capped at the actual output length)

### Requirement: Crash-marker lines surface separately

The gate SHALL scan the FULL `e2e_output` for lines matching crash markers (`Error:`, `Traceback`, `webServer`, `Killed`, `OOM`, `assert`, case-insensitive substring match) and SHALL include the matched lines (with their original line numbers from the output) in a `## Crash markers detected` section ABOVE the tail. This SHALL run independently of the tail cap so a marker on line 5 survives even when the tail is line 800-880.

#### Scenario: Marker outside the tail window is still surfaced

- **GIVEN** `e2e_output` is 1000 lines long
- **AND** an `Error: webServer failed to start on port 3000` appears on line 12
- **AND** the tail cap is 80 (lines 921-1000)
- **WHEN** the gate produces `retry_context`
- **THEN** the `## Crash markers detected` section SHALL include the line-12 entry as `L12: Error: webServer failed to start on port 3000`
- **AND** the `## Stdout/stderr tail (last 80 lines)` section SHALL contain lines 921-1000

#### Scenario: No markers — section omitted

- **GIVEN** `e2e_output` contains no crash markers anywhere
- **WHEN** the gate produces `retry_context`
- **THEN** the `## Crash markers detected` section SHALL NOT appear
- **AND** the `## Stdout/stderr tail` section SHALL still appear

### Requirement: Existing orientation paragraph and self-heal note are preserved

The existing message ("This usually means the suite crashed before completing — check the worktree for stack traces, OOM kills, webServer startup errors, or a Playwright reporter that differs from the default.") and the existing self-heal-attempted suffix SHALL appear UNCHANGED at the top of the new `retry_context`. The new tail/markers sections appear below.

#### Scenario: Orientation paragraph stays at top

- **WHEN** the gate produces `retry_context` for an unparseable failure with no self-heal
- **THEN** the FIRST paragraph SHALL be the existing orientation message verbatim
- **AND** the `## Crash markers detected` (if any) and `## Stdout/stderr tail` sections SHALL appear after a blank line below it

#### Scenario: Self-heal note stays inline with orientation

- **WHEN** the gate ran with `self_heal_pkg` set (an attempted self-heal that also crashed)
- **THEN** the existing `\n\nself-heal attempted for '<pkg>' — rerun also crashed, not a dep-drift issue` SHALL appear immediately after the orientation paragraph
- **AND** the markers and tail sections SHALL appear after that
