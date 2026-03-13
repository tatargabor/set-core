## MODIFIED Requirements

### Requirement: Spec file as orchestration input
The system SHALL accept an arbitrary markdown specification document as the primary input for orchestration via the `--spec <path>` CLI flag. When `--spec` points to a file, the system SHALL route it through the digest pipeline (same as directory input), producing structured requirements, ambiguities, and domain summaries before decomposition.

#### Scenario: Explicit spec file path
- **WHEN** the user runs `wt-orchestrate --spec docs/v1-minishop.md`
- **THEN** the system SHALL set `INPUT_MODE="digest"` and `INPUT_PATH` to the absolute file path
- **AND** auto-trigger `cmd_digest` to produce `wt/orchestration/digest/` output before decomposition

#### Scenario: Explicit spec directory path
- **WHEN** the user runs `wt-orchestrate --spec docs/`
- **THEN** the system SHALL set `INPUT_MODE="digest"` and `INPUT_PATH` to the absolute directory path
- **AND** auto-trigger `cmd_digest` to produce `wt/orchestration/digest/` output before decomposition

#### Scenario: Spec file not found
- **WHEN** the user provides `--spec <path>` and the file does not exist
- **THEN** the system SHALL exit with an error message: "Spec file not found: <path>"

#### Scenario: Spec format agnostic
- **WHEN** a spec document is provided
- **THEN** the system SHALL NOT require any specific section headers (no mandatory `### Next`, `## Feature Roadmap`, etc.)
- **AND** the digest SHALL extract requirements from the document's content regardless of structure

## REMOVED Requirements

### Requirement: INPUT_MODE="spec" code path
The separate `INPUT_MODE="spec"` processing path that passed raw spec content directly to the decompose prompt is removed.

**Reason:** All `--spec` inputs now route through digest, making the raw pass-through path dead code. The digest pipeline handles single files identically to directories.

**Migration:** No user-facing migration needed. Projects using `--spec <file>` will automatically get digest processing with structured requirements output.
