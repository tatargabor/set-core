## MODIFIED Requirements

### Requirement: Execution section in HTML report
The report SHALL display real-time execution progress.

#### Scenario: Change timeline rendering
- **WHEN** changes have execution data in `orchestration-state.json`
- **THEN** the execution section SHALL display each change with: name, status (color-coded), elapsed time, token usage (`tokens_used` field), and iteration count (from worktree `loop-state.json` if accessible)

#### Scenario: Gate results matrix
- **WHEN** changes have gate results in `orchestration-state.json`
- **THEN** the report SHALL display a matrix with columns: test_result, build_result, scope_check, e2e_result, has_tests
- **AND** each cell SHALL show a checkmark for pass, cross for fail, dash for skip/null

#### Scenario: Smoke column with screenshot indicator
- **WHEN** a change has `smoke_screenshot_count > 0` in state.json
- **THEN** the smoke column SHALL display the pass/fail icon followed by a camera icon linking to the screenshot directory
- **AND** the link SHALL point to `../../wt/orchestration/smoke-screenshots/{change-name}/`

#### Scenario: Smoke skip_merged display
- **WHEN** a change has `smoke_result: "skip_merged"`
- **THEN** the smoke column SHALL display a dash with tooltip "Skipped — already merged from previous phase"

#### Scenario: Smoke skip (no command) display
- **WHEN** a change has `smoke_result: "skip"` (no smoke_command configured)
- **THEN** the smoke column SHALL display a dash with tooltip "Skipped — no smoke command configured"

#### Scenario: E2E column with screenshot indicator
- **WHEN** a change has `e2e_screenshot_count > 0` in state.json
- **THEN** the E2E column SHALL display the pass/fail icon followed by a camera icon linking to the screenshot directory
- **AND** the link SHALL point to `../../wt/orchestration/e2e-screenshots/{change-name}/`

#### Scenario: Active issues listing
- **WHEN** changes have non-success states (verify-failed, stalled, merge-blocked, failed)
- **THEN** the report SHALL list each issue with the change name and relevant context (truncated test_output or build_output from state)

#### Scenario: Execution summary stats
- **WHEN** the report is generated during or after execution
- **THEN** it SHALL display: elapsed time (wall + active), total tokens used (sum of all changes' tokens_used), changes completed/running/pending/failed/merge-blocked

## ADDED Requirements

### Requirement: Screenshot gallery in execution section
The report SHALL display an expandable screenshot gallery for changes that have collected Playwright artifacts.

#### Scenario: Inline smoke screenshot gallery
- **WHEN** at least one change has `smoke_screenshot_count > 0`
- **THEN** the report SHALL render a collapsible `<details>` section titled "Smoke Screenshots" after the execution table
- **AND** inside, group by change name, then by attempt subdirectory
- **AND** display up to 8 `.png` images per change (across all attempts, most recent attempt first)
- **AND** each image SHALL be rendered as a clickable thumbnail (max-width: 320px) with filename caption

#### Scenario: Inline E2E screenshot gallery
- **WHEN** at least one change has `e2e_screenshot_count > 0`
- **THEN** the report SHALL render a collapsible `<details>` section titled "E2E Screenshots" after the execution table
- **AND** group screenshots by change name
- **AND** display up to 8 `.png` images per change

#### Scenario: No screenshots available
- **WHEN** no changes have any screenshot artifacts
- **THEN** no gallery section SHALL be rendered (no empty placeholder)
