## ADDED Requirements

### Requirement: Project brief document
The system SHALL support a `openspec/project-brief.md` document as the primary input for orchestration.

#### Scenario: Brief location
- **WHEN** the orchestrator looks for a project brief
- **THEN** it SHALL check for `openspec/project-brief.md` in the project root
- **AND** fall back to `openspec/project.md` if project-brief.md does not exist

#### Scenario: Backwards compatibility
- **WHEN** `openspec/project-brief.md` exists
- **THEN** it SHALL be a valid superset of the existing `project.md` format
- **AND** all existing project.md sections (Purpose, Tech Stack, Conventions, etc.) SHALL remain valid

### Requirement: Feature roadmap section
The project brief SHALL include a `## Feature Roadmap` section with categorized items.

#### Scenario: Roadmap categories
- **WHEN** the brief contains a `## Feature Roadmap` section
- **THEN** it SHALL support these subsections:
  - `### Done`: completed capabilities (informational, not processed by orchestrator)
  - `### Next`: capabilities to implement (orchestrator input)
  - `### Ideas`: future considerations (not processed by orchestrator)

#### Scenario: Next section format
- **WHEN** the `### Next` subsection contains bullet items
- **THEN** each bullet SHALL be a candidate for change decomposition
- **AND** bullets MAY include optional details after a colon (e.g., `- User auth: JWT-based, support OAuth2 providers`)

#### Scenario: Roadmap progression
- **WHEN** a roadmap item's changes are all merged
- **THEN** the developer MAY move the item from `### Next` to `### Done`
- **AND** the orchestrator SHALL NOT track this progression automatically

### Requirement: Orchestrator directives section
The project brief SHALL support a `## Orchestrator Directives` section with key-value configuration.

#### Scenario: Supported directives
- **WHEN** the brief contains `## Orchestrator Directives`
- **THEN** the system SHALL parse the following key-value pairs (one per line, `key: value` format):
  - `max_parallel`: integer, maximum concurrent changes (default: 2)
  - `merge_policy`: one of "eager", "checkpoint", "manual" (default: "checkpoint")
  - `checkpoint_every`: integer, pause after N changes complete (default: 3)
  - `test_command`: string, shell command to run for verification (default: none)
  - `notification`: one of "desktop", "gui", "none" (default: "desktop")
  - `token_budget`: integer, total token limit across all changes — triggers checkpoint when exceeded (default: 0 = unlimited)
  - `pause_on_exit`: boolean, whether to pause Ralph loops when orchestrator exits (default: false)

#### Scenario: Missing directives section
- **WHEN** the brief does not contain `## Orchestrator Directives`
- **THEN** the system SHALL use default values for all directives

#### Scenario: Invalid directive value
- **WHEN** a directive has an unrecognized value (e.g., `merge_policy: yolo`)
- **THEN** the system SHALL print a warning and use the default value for that directive

### Requirement: Brief parsing
The system SHALL reliably parse the project brief markdown document.

#### Scenario: Extract Next items
- **WHEN** the orchestrator parses the brief
- **THEN** it SHALL extract all bullet items under `### Next` as strings
- **AND** strip leading `- ` prefix and any markdown formatting

#### Scenario: Extract directives
- **WHEN** the orchestrator parses the brief
- **THEN** it SHALL extract key-value pairs from lines matching `^- \w+: .+$` or `^\w+: .+$` under `## Orchestrator Directives`

#### Scenario: Compute brief hash
- **WHEN** the orchestrator reads the brief
- **THEN** it SHALL compute SHA-256 of the file contents for staleness detection
