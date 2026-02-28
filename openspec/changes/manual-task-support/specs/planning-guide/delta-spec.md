## ADDED Requirements

### Requirement: Planner generates manual tasks
The planner LLM prompt instructs generation of `[?]` tasks when a change involves external dependencies.

#### Scenario: Change requires API keys or secrets
- **WHEN** a change scope mentions external services (Stripe, Firebase, AWS, etc.)
- **THEN** the planner prompt instructs the LLM to generate `[?]` tasks for credential/secret setup with `[input:KEY_NAME]` annotations

#### Scenario: Change requires external account setup
- **WHEN** a change scope mentions creating accounts, enabling features, or configuring external services
- **THEN** the planner prompt instructs the LLM to generate `[?]` tasks with `[confirm]` annotations

#### Scenario: Manual instruction sections generated
- **WHEN** `[?]` tasks are generated in tasks.md (during ff artifact creation)
- **THEN** corresponding `### Manual:` sections are included with step-by-step instructions, relevant URLs, expected formats, and target file paths

### Requirement: Plan-review checks for missing manual tasks
The plan-review skill flags potential missing manual task markers.

#### Scenario: External service without manual task
- **WHEN** plan-review analyzes a change whose scope mentions external services, API keys, tokens, or webhooks
- **AND** the tasks.md contains no `[?]` tasks
- **THEN** flag a warning: "Change involves external services but has no manual tasks — consider adding [?] tasks for credential/setup steps"

### Requirement: has_manual_tasks plan metadata
The orchestration plan JSON tracks which changes have manual tasks.

#### Scenario: Plan includes manual task flag
- **WHEN** the planner generates a change that will need human intervention
- **THEN** the change object in orchestration-plan.json includes `"has_manual_tasks": true`
- **AND** this is informational only — it does not affect dispatch or scheduling
