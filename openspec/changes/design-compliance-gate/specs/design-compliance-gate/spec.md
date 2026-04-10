## ADDED Requirements

### Requirement: Plugin-registered design compliance gate
The system SHALL provide a web-module plugin gate (`design_compliance`) that runs after the E2E gate and reviews Playwright screenshots against the project's design system via an LLM vision call.

#### Scenario: Gate registered via extra_gates hook
- **WHEN** the verifier assembles the gate pipeline for a web project
- **THEN** the pipeline SHALL include a `design_compliance` gate positioned `after:e2e`
- **AND** the gate SHALL use a dedicated retry counter named `design` isolated from `verify_retry_count`
- **AND** the core verifier pipeline assembly SHALL merge profile-provided gates from `ProjectType.extra_gates()` with core gates

#### Scenario: Gate absent on non-web projects
- **WHEN** the verifier assembles the gate pipeline for a non-web project
- **THEN** the pipeline SHALL NOT include a `design_compliance` gate
- **AND** no design-related code paths SHALL execute

### Requirement: Gate preconditions
The design compliance gate SHALL skip cleanly without LLM calls when any precondition is not met, logging an INFO message with the reason.

#### Scenario: Skip when E2E did not pass
- **GIVEN** the E2E gate result is `fail`, `skipped`, or absent
- **WHEN** the design compliance gate position is reached
- **THEN** the gate SHALL set `design_compliance_result = "skipped"`
- **AND** log `[INFO] design_compliance skipped: e2e did not pass`
- **AND** no LLM call SHALL be made

#### Scenario: Skip when no design files exist
- **GIVEN** neither `docs/design-system.md` nor `docs/design-brief.md` exist
- **WHEN** the gate runs
- **THEN** the gate SHALL set `design_compliance_result = "skipped"`
- **AND** log `[INFO] design_compliance skipped: no design files`

#### Scenario: Skip when no screenshots present
- **GIVEN** all precondition files exist
- **BUT** no PNG files are found under configured screenshot directories
- **WHEN** the gate runs
- **THEN** the gate SHALL set `design_compliance_result = "skipped"`
- **AND** log `[INFO] design_compliance skipped: no screenshots found`

### Requirement: Screenshot sampling strategy
The gate SHALL sample at most `max_screenshots` PNG files from configured directories using deterministic selection: one file per parent directory (the file with the highest mtime), groups sorted alphabetically.

#### Scenario: Sampling picks latest file per test group
- **GIVEN** a `test-results/` tree with three subdirectories (`cart-tests`, `admin-tests`, `auth-tests`), each containing 5 PNG files
- **AND** `max_screenshots = 8`
- **WHEN** the gate samples screenshots
- **THEN** exactly 3 screenshots SHALL be selected (one per group)
- **AND** each selected file SHALL be the one with the highest mtime in its group
- **AND** the selection SHALL be deterministic across runs

#### Scenario: Sampling cap applied
- **GIVEN** 20 test groups exist, each with PNG files
- **AND** `max_screenshots = 8`
- **WHEN** the gate samples screenshots
- **THEN** exactly 8 screenshots SHALL be selected
- **AND** the selected groups SHALL be the first 8 alphabetically

#### Scenario: Sampling walks multiple configured directories
- **GIVEN** `screenshot_dirs = ["test-results", ".playwright/screenshots"]`
- **AND** both directories contain PNG files
- **WHEN** the gate samples screenshots
- **THEN** files from BOTH directories SHALL be considered for grouping

### Requirement: LLM vision review call
The gate SHALL invoke Claude with the sampled screenshots and a prompt built from design tokens and per-page visual descriptions, requesting a JSON response with PASS/WARN/FAIL verdicts and findings.

#### Scenario: Prompt includes design tokens
- **WHEN** the gate builds the LLM prompt
- **THEN** the prompt SHALL include the Design Tokens section from `design-system.md`
- **AND** the prompt SHALL include the matching per-page visual descriptions from `design-brief.md` for pages corresponding to the sampled screenshots
- **AND** the prompt SHALL request a JSON response with per-screenshot `{verdict, findings[]}` entries

#### Scenario: Single multi-image call
- **WHEN** the gate has 5 sampled screenshots
- **THEN** exactly ONE call SHALL be made to `run_claude_logged` with all 5 images attached
- **AND** the call SHALL use `purpose="design_compliance"`
- **AND** the call SHALL use the configured model (default `sonnet`)
- **AND** the call SHALL use the configured timeout (default 300 seconds)

#### Scenario: LLM call fails or times out
- **WHEN** the Claude CLI returns non-zero exit or times out
- **THEN** the gate SHALL set `design_compliance_result = "skipped"` (NOT `"fail"`)
- **AND** log `[WARNING] design_compliance: LLM call failed (exit=N), skipping gate`
- **AND** the pipeline SHALL continue

#### Scenario: LLM response cannot be parsed
- **WHEN** the LLM response is not valid JSON matching the expected schema
- **THEN** the gate SHALL set `design_compliance_result = "skipped"`
- **AND** log `[WARNING] design_compliance: LLM parse error, skipping gate`

### Requirement: Verdict aggregation and fail_on policy
The gate SHALL aggregate per-screenshot verdicts into a single gate result according to the configured `fail_on` policy.

#### Scenario: All screenshots pass
- **GIVEN** the LLM returned PASS for all sampled screenshots
- **WHEN** the gate aggregates the result
- **THEN** the gate result SHALL be `pass`
- **AND** findings SHALL be logged as informational

#### Scenario: fail_on major blocks only on FAIL verdicts
- **GIVEN** `fail_on = "major"`
- **AND** the LLM returned 2 WARN and 0 FAIL verdicts
- **WHEN** the gate aggregates the result
- **THEN** the gate result SHALL be `pass`
- **AND** WARN findings SHALL be logged but not block the pipeline

#### Scenario: fail_on major fails on FAIL verdict
- **GIVEN** `fail_on = "major"`
- **AND** the LLM returned 1 FAIL verdict
- **WHEN** the gate aggregates the result
- **THEN** the gate result SHALL be `fail`
- **AND** the FAIL findings SHALL be written to the change's `retry_context`

#### Scenario: fail_on any blocks on WARN
- **GIVEN** `fail_on = "any"`
- **AND** the LLM returned 1 WARN verdict
- **WHEN** the gate aggregates the result
- **THEN** the gate result SHALL be `fail`

#### Scenario: fail_on never never blocks
- **GIVEN** `fail_on = "never"`
- **AND** the LLM returned 3 FAIL verdicts
- **WHEN** the gate aggregates the result
- **THEN** the gate result SHALL be `pass`
- **AND** all findings SHALL be logged as informational

### Requirement: Dedicated retry budget
The design compliance gate SHALL use a dedicated retry counter (`design_retry_count`) isolated from the shared verify retry counter, allowing up to `max_retries` (default 3) redispatches on FAIL verdicts.

#### Scenario: Design fail triggers redispatch with actionable context
- **GIVEN** the gate returns `fail` with specific findings
- **AND** `design_retry_count < max_retries`
- **WHEN** the verifier processes the fail
- **THEN** the change SHALL be redispatched to the agent
- **AND** the agent SHALL receive the findings via `retry_context`
- **AND** `design_retry_count` SHALL be incremented by 1
- **AND** `verify_retry_count` SHALL NOT be affected

#### Scenario: Design retries exhausted
- **GIVEN** `design_retry_count` has reached `max_retries`
- **WHEN** the gate would fail again
- **THEN** the gate SHALL set `design_compliance_result = "exhausted"`
- **AND** log `[WARNING] design_compliance: retries exhausted (N/max), marking design-exhausted`
- **AND** the fail_on policy SHALL decide whether the change is blocked or merged with warnings

#### Scenario: Design counter isolated from verify counter
- **GIVEN** `verify_retry_count = 2` (from prior test failures)
- **AND** `design_retry_count = 0`
- **WHEN** the design gate fails twice
- **THEN** `design_retry_count` SHALL equal 2
- **AND** `verify_retry_count` SHALL still equal 2
- **AND** both counters SHALL decrement independently toward their own max

### Requirement: Findings persistence and state exposure
The gate SHALL persist findings to the worktree and expose the gate result on the change state for API consumers.

#### Scenario: Findings written to worktree file
- **WHEN** the gate completes (pass or fail)
- **THEN** findings SHALL be appended to `.set/gates/design_compliance_findings.jsonl` in the worktree
- **AND** each line SHALL be a JSON object with `{screenshot_path, verdict, findings[], timestamp}`

#### Scenario: State fields updated
- **WHEN** the gate completes
- **THEN** the change state SHALL have `design_compliance_result` set to the verdict (`pass`, `fail`, `skipped`, or `exhausted`)
- **AND** `gate_design_compliance_ms` SHALL contain the elapsed milliseconds of the gate run
- **AND** `state.change.extras.design_findings` SHALL contain the parsed findings list

### Requirement: Configuration schema
The design compliance gate SHALL be configurable via a `design_compliance` block in `set/orchestration/config.yaml` with sensible defaults.

#### Scenario: Defaults applied when config missing
- **GIVEN** `set/orchestration/config.yaml` has no `design_compliance` block
- **WHEN** the gate runs
- **THEN** `enabled = true`, `model = "sonnet"`, `max_screenshots = 8`, `fail_on = "major"`, `max_retries = 3`, `timeout = 300`, `screenshot_dirs = ["test-results", ".playwright/screenshots"]` SHALL be used

#### Scenario: User overrides applied
- **GIVEN** the config specifies `design_compliance.max_retries: 5` and `design_compliance.fail_on: "any"`
- **WHEN** the gate runs
- **THEN** the overridden values SHALL be used
- **AND** other keys SHALL use defaults

#### Scenario: Master enable toggle disables gate
- **GIVEN** the config specifies `design_compliance.enabled: false`
- **WHEN** the verifier assembles the gate pipeline
- **THEN** the `design_compliance` gate SHALL NOT be registered
- **AND** no screenshots SHALL be inspected

### Requirement: Web dashboard exposure
The web dashboard SHALL display the design compliance gate status and allow users to drill into findings.

#### Scenario: D icon in GateBar
- **WHEN** a change has `design_compliance_result` set
- **THEN** the `GateBar` component SHALL render a `D` icon between `E` and `R`
- **AND** the icon color SHALL reflect the result (green pass, amber warn/exhausted, red fail, grey skipped)

#### Scenario: Findings modal
- **WHEN** the user clicks the D gate icon
- **AND** findings exist for that change
- **THEN** a modal SHALL open showing each finding with its screenshot path, verdict, and issue list

#### Scenario: ChangeInfo API exposure
- **WHEN** the orchestration API returns change info
- **THEN** the response SHALL include `design_compliance_result`, `gate_design_compliance_ms`, and `design_retry_count`
