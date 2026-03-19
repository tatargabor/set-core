## ADDED Requirements

### Requirement: Brief format backward compatibility
The system SHALL continue to support the existing `project-brief.md` format with `### Next` section as a valid input.

#### Scenario: Brief with Next section
- **WHEN** `openspec/project-brief.md` exists and contains a `### Next` section with bullet items
- **THEN** the system SHALL use bash-based `parse_next_items()` for fast extraction (no API call needed)
- **AND** the behavior SHALL be identical to the pre-refactor implementation

#### Scenario: Brief with Orchestrator Directives
- **WHEN** the brief contains an `## Orchestrator Directives` section
- **THEN** the system SHALL parse it with the existing `parse_directives()` function
- **AND** these values SHALL participate in the directive precedence chain (below CLI flags and `.claude/orchestration.yaml`, above defaults)

### Requirement: Brief as spec fallback
The system SHALL treat a brief with an empty `### Next` section as a candidate for LLM extraction.

#### Scenario: Brief with empty Next
- **WHEN** `project-brief.md` exists but `### Next` has no bullet items
- **AND** `--spec` is not provided
- **THEN** the system SHALL NOT fall through to the LLM extraction path
- **AND** SHALL exit with an error suggesting to add items to `### Next` or use `--spec`

### Requirement: Template update
The `project-brief.md.template` SHALL mention the `--spec` alternative for users with existing spec documents.

#### Scenario: Template content
- **WHEN** a new project runs `openspec init` or copies the template
- **THEN** the template SHALL include a comment explaining: "If you already have a specification document, use `set-orchestrate --spec <path>` instead of maintaining this brief separately"
