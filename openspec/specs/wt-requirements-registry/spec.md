## ADDED Requirements

### Requirement: Requirement file format
Business requirements SHALL be stored in `wt/requirements/` in one of two formats: structured YAML or rich markdown. Both are valid and the planner reads both.

#### Scenario: YAML requirement file
- **WHEN** a structured requirement is created (manually or by tooling)
- **THEN** it is stored as `REQ-{NNN}-{kebab-name}.yaml` with required fields:
  - `id`: string matching `REQ-{NNN}` pattern
  - `title`: human-readable title
  - `status`: one of `captured`, `planned`, `in_progress`, `implemented`, `deferred`
  - `priority`: one of `must`, `should`, `could`
  - `description`: multi-line text describing the requirement

#### Scenario: Markdown requirement file
- **WHEN** a rich requirement is captured (e.g., by set-spec-capture from a website)
- **THEN** it is stored as `{session-name}.md` in `wt/requirements/`
- **AND** the file contains a YAML frontmatter block with at minimum `status` and `source` fields
- **AND** the body contains the detailed requirement description, screenshots, or annotated content

#### Scenario: Optional fields for YAML format
- **WHEN** a YAML requirement file is created
- **THEN** it MAY contain the following optional fields:
  - `source`: one of `manual`, `set-spec-capture`, `stakeholder` (default: `manual`)
  - `acceptance_criteria`: list of testable criteria strings
  - `links.changes`: list of OpenSpec change names this requirement maps to
  - `links.specs`: list of OpenSpec spec names related to this requirement
  - `links.features`: list of project-knowledge feature names
  - `created`: ISO date
  - `updated`: ISO date

### Requirement: Requirements are planner input
The planner SHALL be able to read `wt/requirements/*.yaml` files and use them as context for plan decomposition.

#### Scenario: Requirements inform planning
- **WHEN** the planner generates a plan from a spec or brief
- **AND** `wt/requirements/` contains requirement files with status `planned` or `captured`
- **THEN** the planner includes requirement titles and descriptions in the decomposition context

#### Scenario: No requirements directory
- **WHEN** the planner generates a plan
- **AND** `wt/requirements/` does not exist or is empty
- **THEN** the planner proceeds normally without requirement context (graceful degradation)

### Requirement: Requirement status lifecycle
Requirements SHALL follow a defined status lifecycle that tracks their progress from capture to implementation.

#### Scenario: Status transitions
- **WHEN** a requirement is created (manually or via set-spec-capture)
- **THEN** its initial status is `captured`
- **WHEN** a requirement is included in an orchestration plan
- **THEN** its status transitions to `planned`
- **WHEN** an OpenSpec change linked to the requirement is dispatched
- **THEN** its status transitions to `in_progress`
- **WHEN** all linked OpenSpec changes are merged
- **THEN** its status transitions to `implemented`

#### Scenario: Deferred requirement
- **WHEN** a user decides to postpone a requirement
- **THEN** its status is set to `deferred` with an optional reason in the description

### Requirement: set-spec-capture output compatibility
The requirement file format SHALL be compatible with set-spec-capture Chrome extension output, allowing captured specifications to be saved directly as requirement files.

#### Scenario: Chrome extension generates requirement
- **WHEN** set-spec-capture exports a captured specification
- **THEN** the output is a valid `REQ-{NNN}-{name}.yaml` file with `source: set-spec-capture`
- **AND** the file can be placed directly in `wt/requirements/`
