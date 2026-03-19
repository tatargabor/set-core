## ADDED Requirements

### Requirement: Documentation Generation
The system SHALL generate Markdown documentation from OpenSpec spec files.

#### Scenario: Generate documentation from specs
- **WHEN** user runs `docs-gen`
- **THEN** all spec files are parsed from `openspec/specs/` and active changes
- **AND** a consolidated `docs/confluence.md` file is generated
- **AND** the file includes last-updated timestamp

#### Scenario: Parse Requirements into sections
- **WHEN** a spec file contains `### Requirement: <name>`
- **THEN** a corresponding section is created in the documentation
- **AND** the requirement description is included

#### Scenario: Parse Scenarios into examples
- **WHEN** a requirement has `#### Scenario: <name>` blocks
- **THEN** each scenario is converted to a usage example
- **AND** WHEN clauses become command examples
- **AND** THEN clauses become expected results

#### Scenario: No spec files found
- **WHEN** user runs `docs-gen` and no spec files exist
- **THEN** an informative error is displayed
- **AND** no output file is created

### Requirement: Tutorial Generation
The system SHALL generate a step-by-step tutorial section for new users.

#### Scenario: Generate tutorial from key scenarios
- **WHEN** documentation is generated
- **THEN** a "Quick Start" section is created
- **AND** it contains ordered steps for: Installation, Project setup, First worktree, Editing

#### Scenario: Tutorial references detailed sections
- **WHEN** tutorial mentions a command
- **THEN** a link or reference to the detailed command documentation is included

### Requirement: Reference Section Generation
The system SHALL generate a complete command reference section.

#### Scenario: Generate reference for each command
- **WHEN** documentation is generated
- **THEN** each wt-* command has its own subsection
- **AND** all scenarios for that command are included as examples
- **AND** options and flags are documented

#### Scenario: Order commands logically
- **WHEN** reference section is generated
- **THEN** commands are ordered: set-project, wt-open, wt-edit, wt-list, wt-close
- **AND** installation is documented separately

### Requirement: Confluence Compatibility
The system SHALL generate documentation compatible with Confluence Markdown import.

#### Scenario: Use basic Markdown syntax
- **WHEN** documentation is generated
- **THEN** only basic Markdown is used (headers, lists, code blocks, bold)
- **AND** no Confluence-specific macros are required

#### Scenario: Code blocks are formatted
- **WHEN** command examples are generated
- **THEN** bash code blocks with syntax highlighting hints are used
- **AND** expected output is shown in separate blocks or comments

### Requirement: Incremental Updates
The system SHALL support regeneration when specs change.

#### Scenario: Regenerate after spec change
- **WHEN** user modifies a spec file and runs `docs-gen`
- **THEN** the documentation is regenerated with updated content
- **AND** the timestamp is updated

#### Scenario: Diff-friendly output
- **WHEN** only one spec changes
- **THEN** the regenerated documentation changes only the affected sections
- **AND** unaffected sections remain identical (for clean git diffs)
