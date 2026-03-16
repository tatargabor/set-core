## ADDED Requirements

### Requirement: Tasks reference requirement IDs
Each task in tasks.md SHALL include a `[REQ: <requirement-name>]` tag linking it to the spec requirement it implements. The ff-change skill instruction SHALL make this tagging mandatory for all implementation tasks. The requirement name SHALL be a kebab-case slug of the `### Requirement:` header text. Matching SHALL be case-insensitive and whitespace-tolerant.

#### Scenario: Task generated with requirement tag
- **WHEN** the ff-change skill generates tasks.md from specs
- **THEN** each implementation task SHALL include a `[REQ: <requirement-name>]` tag
- **AND** the requirement name SHALL match a `### Requirement:` header from the delta specs

#### Scenario: Task without requirement tag detected by verify
- **WHEN** the verify skill parses tasks.md and finds a task without a `[REQ: ...]` tag
- **THEN** it SHALL report a WARNING: "Task without requirement link: <task description>"
- **AND** the recommendation SHALL be: "Add [REQ: <name>] tag to link this task to a spec requirement"

#### Scenario: Requirement with no tasks detected by verify
- **WHEN** the verify skill cross-references spec requirements against task REQ tags
- **AND** a requirement from the delta specs has no corresponding task
- **THEN** it SHALL report a CRITICAL issue: "Requirement not covered by any task: <requirement name>"

#### Scenario: Unresolved requirement reference in task
- **WHEN** the verify skill finds a `[REQ: <name>]` tag in tasks.md
- **AND** the name does not match any `### Requirement:` header in the delta specs (after kebab-case normalization)
- **THEN** it SHALL report a WARNING: "Unresolved requirement reference: <name>"

### Requirement: Verify generates traceability matrix
The verify-change skill SHALL generate a traceability matrix showing which requirements are covered by which tasks, computed dynamically from tasks.md content and delta spec requirements.

#### Scenario: All requirements covered
- **WHEN** the verify skill generates the traceability matrix
- **AND** every delta spec requirement has at least one task with a matching `[REQ: ...]` tag
- **THEN** the matrix SHALL show all requirements with status "Covered"

#### Scenario: Uncovered requirement in matrix
- **WHEN** the verify skill generates the traceability matrix
- **AND** a requirement has no matching task
- **THEN** the matrix SHALL show that requirement with status "MISSING"
- **AND** a CRITICAL issue SHALL be reported

#### Scenario: Matrix output format
- **WHEN** the traceability matrix is generated
- **THEN** it SHALL be formatted as a markdown table with columns: Requirement, Tasks, Status
- **AND** it SHALL appear in the verification report under "## Traceability Matrix"
