## ADDED Requirements

### Requirement: Python audit pipeline
The system SHALL provide `run_post_phase_audit()` in `lib/set_orch/auditor.py` that replicates the full bash audit pipeline: input JSON construction, Claude API call for gap detection, result parsing, and state update with replan context injection.

#### Scenario: Successful audit
- **WHEN** `set-orch-core audit run --state-file <path>` is invoked after a phase completes
- **THEN** the system builds audit input from merged changes, calls Claude for gap analysis, parses the result, and updates state with findings

#### Scenario: Audit with critical gaps
- **WHEN** the audit detects critical gaps in requirement coverage
- **THEN** `_REPLAN_AUDIT_GAPS` context is exported for the replan cycle

#### Scenario: Parse failure is non-blocking
- **WHEN** the Claude response cannot be parsed as valid JSON
- **THEN** the audit logs the error and returns status 0 (non-blocking)

### Requirement: Python audit input builder
The system SHALL provide `build_audit_input()` in `auditor.py` that constructs the JSON input for the audit template, including merged changes, scopes, requirements, and diff data.

#### Scenario: Input construction with spec mode
- **WHEN** specs exist and audit mode is "spec"
- **THEN** the input includes requirement IDs and spec references

#### Scenario: Input construction with digest mode
- **WHEN** no specs exist and audit mode is "digest"
- **THEN** the input includes digest-level requirement data

### Requirement: Python audit result parser
The system SHALL provide `parse_audit_result()` in `auditor.py` that extracts structured JSON from Claude's audit response, classifying findings by severity (critical, minor).

#### Scenario: Structured result extraction
- **WHEN** Claude returns a response containing JSON audit findings
- **THEN** the parser extracts the JSON block and returns typed findings

### Requirement: Bash auditor.sh becomes thin wrapper
After migration, `auditor.sh` SHALL contain only delegation to `set-orch-core audit run`.

#### Scenario: Thin wrapper delegation
- **WHEN** `run_post_phase_audit()` is called in bash
- **THEN** it delegates to `set-orch-core audit run` with equivalent arguments
