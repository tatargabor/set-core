### Requirement: Post-phase audit execution
The orchestrator SHALL run an LLM-driven spec-vs-implementation audit after all changes in a phase are resolved (merged, failed, or skipped).

#### Scenario: Audit triggered before replan
- **WHEN** all changes are resolved and `auto_replan` is `true`
- **AND** `post_phase_audit` is not `false`
- **THEN** the orchestrator SHALL call `run_post_phase_audit()` before `auto_replan_cycle()`
- **AND** store the gap report in state as `phase_audit_result`
- **AND** export the gap descriptions via `_REPLAN_AUDIT_GAPS` for the replan prompt

#### Scenario: Audit triggered at terminal state
- **WHEN** all changes are resolved and `auto_replan` is `false`
- **AND** `post_phase_audit` is `true`
- **THEN** the orchestrator SHALL call `run_post_phase_audit()` before generating the completion report
- **AND** include the gap summary in the report and email notification

#### Scenario: Audit disabled
- **WHEN** `post_phase_audit` is explicitly `false`
- **THEN** the orchestrator SHALL skip the audit entirely

#### Scenario: Audit defaults
- **WHEN** `post_phase_audit` is not set in orchestration.yaml
- **THEN** the default SHALL be `true` when `auto_replan` is `true`, and `false` otherwise

### Requirement: Audit prompt construction
The audit SHALL compare the input spec against merged change evidence.

#### Scenario: Digest mode audit
- **WHEN** `requirements.json` exists in the digest directory
- **THEN** `build_audit_prompt()` SHALL include all requirement IDs with titles and briefs
- **AND** include coverage status from `coverage.json` (which REQ-IDs are marked merged vs uncovered vs failed)
- **AND** include the file list per merged change (from git log)
- **AND** ask the LLM to identify requirements with no implementation evidence

#### Scenario: Spec/brief mode audit
- **WHEN** no digest exists (spec or brief input mode)
- **THEN** `build_audit_prompt()` SHALL include the raw input spec text (truncated to 30000 chars)
- **AND** include the list of merged changes with their scopes and file lists
- **AND** ask the LLM to identify spec sections with no corresponding implementation

### Requirement: Structured gap report output
The audit LLM output SHALL be parsed into a structured JSON gap report.

#### Scenario: Gaps found
- **WHEN** the LLM identifies missing or incomplete features
- **THEN** the output SHALL be parsed for a JSON block containing:
  - `audit_result`: `"gaps_found"`
  - `gaps[]`: array of objects with `id`, `description`, `spec_reference`, `severity` (critical/minor), `suggested_scope`
  - `summary`: human-readable summary string
- **AND** the gap report SHALL be stored in state as `phase_audit_result`
- **AND** an `AUDIT_GAPS` event SHALL be emitted with gap count and severity breakdown

#### Scenario: No gaps found
- **WHEN** the LLM finds no missing features
- **THEN** the output SHALL contain `audit_result: "clean"`
- **AND** the audit SHALL log success and continue without intervention

#### Scenario: Audit output unparseable
- **WHEN** the LLM output does not contain valid JSON
- **THEN** the audit SHALL log a warning and store the raw output as `phase_audit_raw`
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
