## ADDED Requirements

### Requirement: Plan validate CLI subcommand
`set-orch-core plan validate --plan-file <path> [--digest-dir <path>]` SHALL validate the plan and output errors/warnings to stdout as JSON.

#### Scenario: Valid plan
- **WHEN** the plan passes all validation checks
- **THEN** exit code is 0 and output is `{"errors": [], "warnings": []}`

#### Scenario: Invalid plan
- **WHEN** the plan has validation errors
- **THEN** exit code is 1 and output contains the error list

#### Scenario: Digest mode validation
- **WHEN** --digest-dir is provided
- **THEN** requirement coverage validation is also performed

### Requirement: Plan detect-test-infra CLI subcommand
`set-orch-core plan detect-test-infra [--project-dir <path>]` SHALL scan the project and output test infrastructure info as JSON.

#### Scenario: Detect test framework
- **WHEN** the command is run in a project with vitest
- **THEN** output is `{"framework": "vitest", "config_exists": true, "test_file_count": N, "has_helpers": bool, "test_command": "..."}`

#### Scenario: Default project directory
- **WHEN** --project-dir is not provided
- **THEN** the current directory is scanned

### Requirement: Plan check-triage CLI subcommand
`set-orch-core plan check-triage --digest-dir <path> [--auto-defer]` SHALL check triage gate status and output the result as a plain string.

#### Scenario: Triage passed
- **WHEN** all ambiguities are triaged
- **THEN** output is "passed" and exit code is 0

#### Scenario: Triage needed
- **WHEN** ambiguities exist without triage
- **THEN** output is "needs_triage" and exit code is 0

### Requirement: Plan check-scope-overlap CLI subcommand
`set-orch-core plan check-scope-overlap --plan-file <path> [--state-file <path>] [--pk-file <path>]` SHALL check scope overlap and output warnings as JSON.

#### Scenario: No overlaps
- **WHEN** no scope overlaps are detected
- **THEN** output is `{"warnings": []}` and exit code is 0

#### Scenario: Overlaps found
- **WHEN** overlaps are detected
- **THEN** output contains warnings with change names and similarity percentages

### Requirement: Plan build-context CLI subcommand
`set-orch-core plan build-context --input-file <json>` SHALL assemble decomposition context from the input JSON and output the rendered planning prompt to stdout.

#### Scenario: Spec mode prompt
- **WHEN** input JSON has mode "spec"
- **THEN** the rendered planning prompt for spec/digest mode is output

#### Scenario: Brief mode prompt
- **WHEN** input JSON has mode "brief"
- **THEN** the rendered planning prompt for brief mode is output

### Requirement: Plan enrich-metadata CLI subcommand
`set-orch-core plan enrich-metadata --plan-file <path> --hash <str> --input-mode <str> --input-path <path> [--replan-cycle <int>] [--state-file <path>]` SHALL add metadata to the plan and write the enriched version back.

#### Scenario: Initial plan enrichment
- **WHEN** --replan-cycle is not provided
- **THEN** the plan is enriched with version, hash, timestamps, plan_phase "initial"

#### Scenario: Replan enrichment
- **WHEN** --replan-cycle is provided with --state-file
- **THEN** the plan is enriched with plan_phase "iteration" and completed depends_on references are stripped

### Requirement: Plan summarize-spec CLI subcommand
`set-orch-core plan summarize-spec --spec-file <path> [--phase-hint <str>] [--model <str>]` SHALL summarize a large spec and output the summary to stdout.

#### Scenario: Spec summarization
- **WHEN** the spec file is large
- **THEN** a structured summary is output

### Requirement: Plan replan-context CLI subcommand
`set-orch-core plan replan-context --state-file <path>` SHALL collect replan context and output it as JSON.

#### Scenario: Replan context with completed changes
- **WHEN** the state has merged changes
- **THEN** output JSON includes completed names, roadmap items, file lists, and E2E failure context
