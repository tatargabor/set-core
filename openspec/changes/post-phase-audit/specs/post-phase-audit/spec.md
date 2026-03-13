### Requirement: Post-phase audit execution
The orchestrator SHALL run an LLM-driven spec-vs-implementation audit after all changes in a phase are resolved (merged, failed, or skipped).

#### Scenario: Audit triggered before replan
- **WHEN** all changes are resolved and `auto_replan` is `true`
- **AND** `post_phase_audit` is not `false`
- **THEN** the orchestrator SHALL call `run_post_phase_audit()` before `auto_replan_cycle()`
- **AND** append the gap report to state `phase_audit_results[]` array
- **AND** export the gap descriptions via `_REPLAN_AUDIT_GAPS` for the replan prompt

#### Scenario: Audit triggered at terminal state
- **WHEN** all changes are resolved and `auto_replan` is `false` or replan found no new work
- **AND** `post_phase_audit` is not `false`
- **THEN** the orchestrator SHALL call `run_post_phase_audit()` before generating the completion report
- **AND** include the gap summary in the report and email notification

#### Scenario: Audit disabled
- **WHEN** `post_phase_audit` is explicitly `false`
- **THEN** the orchestrator SHALL skip the audit entirely

#### Scenario: Audit defaults
- **WHEN** `post_phase_audit` is not set in orchestration.yaml
- **THEN** the default SHALL be `true` (always enabled)

### Requirement: Audit prompt construction
The audit SHALL compare the input spec against merged change evidence.

#### Scenario: Digest mode audit
- **WHEN** `requirements.json` exists in the digest directory
- **THEN** `build_audit_prompt()` SHALL include all requirement IDs with titles and briefs
- **AND** include coverage status from `coverage.json` (which REQ-IDs are marked merged vs uncovered vs failed)
- **AND** include the file list per merged change (from git log on main)
- **AND** ask the LLM to identify requirements with no implementation evidence

#### Scenario: Spec/brief mode audit
- **WHEN** no digest exists (spec or brief input mode)
- **THEN** `build_audit_prompt()` SHALL include the raw input spec text (truncated to 30000 chars)
- **AND** include the list of merged changes with their scopes and file lists
- **AND** ask the LLM to identify spec sections with no corresponding implementation

#### Scenario: Prompt template
- **THEN** the prompt SHALL be built via `wt-orch-core template audit --input-file -`
- **AND** the template SHALL be `render_audit_prompt()` in `lib/wt_orch/templates.py` (Python f-string, same pattern as existing templates)

### Requirement: Structured gap report output
The audit LLM output SHALL be parsed into a structured JSON gap report.

#### Scenario: Gaps found
- **WHEN** the LLM identifies missing or incomplete features
- **THEN** the output SHALL be parsed for a JSON block containing:
  - `audit_result`: `"gaps_found"`
  - `gaps[]`: array of objects with `id`, `description`, `spec_reference`, `severity` (critical/minor), `suggested_scope`
  - `summary`: human-readable summary string
- **AND** the gap report SHALL be appended to state `phase_audit_results[]` with cycle, timestamp, model, duration_ms
- **AND** an `AUDIT_GAPS` event SHALL be emitted with gap count and severity breakdown

#### Scenario: No gaps found
- **WHEN** the LLM finds no missing features
- **THEN** the output SHALL contain `audit_result: "clean"`
- **AND** the result SHALL be appended to state `phase_audit_results[]`
- **AND** an `AUDIT_CLEAN` event SHALL be emitted
- **AND** the audit SHALL log success and continue without intervention

#### Scenario: Audit output unparseable
- **WHEN** the LLM output does not contain valid JSON
- **THEN** the audit SHALL log a warning and store the raw output as `phase_audit_raw` in the result entry
- **AND** SHALL NOT block replan or termination (graceful degradation)

### Requirement: Gap injection into replan prompt
The replan cycle SHALL receive audit gap data to prioritize unimplemented features.

#### Scenario: Replan with audit gaps
- **WHEN** `_REPLAN_AUDIT_GAPS` is set and non-empty
- **THEN** the replan prompt SHALL include a section: "Post-phase audit found these gaps — prioritize them in the next plan"
- **AND** list each gap with its description and suggested scope
- **AND** instruct the planner to create dedicated changes for critical gaps

#### Scenario: Replan without audit (disabled or clean)
- **WHEN** `_REPLAN_AUDIT_GAPS` is empty or unset
- **THEN** the replan prompt SHALL proceed without audit context (existing behavior)

### Requirement: Audit model and cost control
The audit SHALL use a cost-efficient model and bounded input size.

#### Scenario: Model selection
- **WHEN** running the audit LLM call
- **THEN** the audit SHALL use the `review_model` (default: sonnet) for the LLM call
- **AND** truncate the input spec to 30000 characters
- **AND** truncate the change file lists to 50 files per change

#### Scenario: Audit timeout
- **WHEN** the audit LLM call takes longer than 120 seconds
- **THEN** the audit SHALL timeout, log a warning, and proceed without blocking

### Requirement: Audit logging
The audit SHALL produce structured logs at multiple levels.

#### Scenario: Event log
- **WHEN** audit starts
- **THEN** emit `AUDIT_START` event with `{cycle, mode, model}`
- **WHEN** audit completes
- **THEN** emit `AUDIT_GAPS` with `{cycle, gap_count, critical_count, minor_count, duration_ms}` or `AUDIT_CLEAN` with `{cycle, duration_ms}`

#### Scenario: Orchestration log
- **WHEN** audit completes
- **THEN** log one-line summary: "Post-phase audit cycle N: X gaps (Y critical, Z minor) in Ns" or "Post-phase audit cycle N: clean in Ns"

#### Scenario: Debug log
- **WHEN** audit completes
- **THEN** write full audit prompt and raw LLM response to `wt/orchestration/audit-cycle-N.log`

### Requirement: HTML report section
The orchestration HTML report SHALL include an audit results section.

#### Scenario: Audit results in report
- **WHEN** `phase_audit_results[]` exists in state and is non-empty
- **THEN** `render_audit_section()` SHALL render a section between execution and coverage
- **AND** show per-cycle: result badge (gaps_found=red, clean=green), model, duration
- **AND** for gaps_found: render gap table with severity color coding (critical=red bg, minor=yellow bg)
- **AND** each gap row: ID, severity, description, spec reference, suggested scope

#### Scenario: No audit results
- **WHEN** `phase_audit_results` is empty or missing
- **THEN** the section SHALL not be rendered

### Requirement: Web dashboard AuditPanel
The wt-web dashboard SHALL visualize audit results.

#### Scenario: AuditPanel rendering
- **WHEN** `phase_audit_results[]` exists in state and is non-empty
- **THEN** AuditPanel SHALL render after ChangeTable on the Dashboard page
- **AND** show summary bar per cycle: gap count with severity badge, color-coded
- **AND** show gap table: ID, severity (color chip), description, spec reference, suggested scope
- **AND** for clean results: green "All spec sections covered" banner

#### Scenario: Multiple phases
- **WHEN** multiple audit results exist (multi-phase orchestration)
- **THEN** AuditPanel SHALL show results in a collapsible accordion per cycle

#### Scenario: No audit data
- **WHEN** `phase_audit_results` is empty or missing from state
- **THEN** AuditPanel SHALL not render
