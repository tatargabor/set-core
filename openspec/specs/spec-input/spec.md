# spec-input Specification

## Purpose
TBD - created by archiving change spec-driven-orchestration. Update Purpose after archive.
## Requirements
### Requirement: Spec file as orchestration input
The system SHALL accept an arbitrary markdown specification document as the primary input for orchestration via the `--spec <path>` CLI flag. When `--spec` points to a file, the system SHALL route it through the digest pipeline (same as directory input), producing structured requirements, ambiguities, and domain summaries before decomposition.

#### Scenario: Explicit spec file path
- **WHEN** the user runs `set-orchestrate --spec docs/v1-minishop.md`
- **THEN** the system SHALL set `INPUT_MODE="digest"` and `INPUT_PATH` to the absolute file path
- **AND** auto-trigger `cmd_digest` to produce `wt/orchestration/digest/` output before decomposition

#### Scenario: Explicit spec directory path
- **WHEN** the user runs `set-orchestrate --spec docs/`
- **THEN** the system SHALL set `INPUT_MODE="digest"` and `INPUT_PATH` to the absolute directory path
- **AND** auto-trigger `cmd_digest` to produce `wt/orchestration/digest/` output before decomposition

#### Scenario: Spec file not found
- **WHEN** the user provides `--spec <path>` and the file does not exist
- **THEN** the system SHALL exit with an error message: "Spec file not found: <path>"

#### Scenario: Spec format agnostic
- **WHEN** a spec document is provided
- **THEN** the system SHALL NOT require any specific section headers (no mandatory `### Next`, `## Feature Roadmap`, etc.)
- **AND** the digest SHALL extract requirements from the document's content regardless of structure

### Requirement: LLM-based extraction of actionable items
The system SHALL use a Claude API call to determine which items from the spec should be implemented next, replacing bash regex parsing for spec input.

#### Scenario: Auto-detection of next batch
- **WHEN** a spec is provided without a `--phase` flag
- **THEN** the LLM SHALL analyze the document for status markers (checkboxes, emoji, "done"/"implemented" text, priority labels, phase numbering)
- **AND** determine the first incomplete batch of work
- **AND** include a `phase_detected` field in the plan JSON explaining which section/phase was selected and why

#### Scenario: Explicit phase hint
- **WHEN** the user provides `--phase <hint>` alongside `--spec`
- **THEN** the LLM prompt SHALL include the hint as guidance: "The user requested phase: <hint>"
- **AND** the LLM SHALL focus decomposition on items matching that phase

#### Scenario: Phase hint as number
- **WHEN** `--phase` value is a number (e.g., `1`, `2`)
- **THEN** the system SHALL pass it as "phase/priority number <N>" to the LLM

#### Scenario: Phase hint as string
- **WHEN** `--phase` value is a non-numeric string (e.g., `"Security fixes"`)
- **THEN** the system SHALL pass it as a descriptive hint to the LLM

### Requirement: Hierarchical summarization for large specs
The system SHALL summarize large specification documents before decomposition to maintain quality.

#### Scenario: Small spec (under threshold)
- **WHEN** the spec content is under ~8000 tokens (estimated as word_count * 1.3)
- **THEN** the full spec content SHALL be passed directly to the decomposition prompt

#### Scenario: Large spec (over threshold)
- **WHEN** the spec content exceeds ~8000 tokens
- **THEN** the system SHALL make a preliminary Claude call to produce a structured summary
- **AND** the summary SHALL include: section headers with completion status, and the full content of the next actionable phase/section
- **AND** the decomposition prompt SHALL use this summary instead of the full document

#### Scenario: Summarization output format
- **WHEN** the summarization call completes
- **THEN** the output SHALL be a markdown document containing a TOC with status markers and the extracted relevant section
- **AND** this summary SHALL be no larger than ~4000 tokens

### Requirement: Input auto-detection fallback
The system SHALL fall back gracefully when neither `--spec` nor `--brief` is provided.

#### Scenario: Auto-detect with project-brief.md present
- **WHEN** no `--spec` or `--brief` flag is given
- **AND** `openspec/project-brief.md` exists with a `### Next` section containing items
- **THEN** the system SHALL use the existing bash-parsed brief path

#### Scenario: Auto-detect with no brief
- **WHEN** no `--spec` or `--brief` flag is given
- **AND** no valid `project-brief.md` is found (or its `### Next` is empty)
- **THEN** the system SHALL exit with an error suggesting: "No project brief found. Use --spec <path> to provide a specification document, or create openspec/project-brief.md"

