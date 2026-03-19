## Requirements

### Requirement: README Guide Document
The project SHALL have a `docs/readme-guide.md` file that defines the authoritative structure, mandatory sections, and rules for the project README.

#### Scenario: Guide file exists
- **WHEN** a contributor looks for documentation standards
- **THEN** `docs/readme-guide.md` exists and contains the complete guide

### Requirement: Mandatory README Sections
The guide SHALL define the following mandatory sections in order:
1. Project title and one-line tagline
2. Overview (3-5 sentences + screenshot)
3. Platform & Editor Support table
4. Quick Start (install → first worktree)
5. Features overview (GUI, CLI, Ralph Loop, Team Sync, OpenSpec, MCP)
6. Installation (detailed)
7. CLI Reference (all user-facing commands)
8. Configuration
9. Known Issues & Limitations
10. Contributing (link to CONTRIBUTING.md)
11. Architecture (brief diagram)
12. Related Projects
13. License

#### Scenario: README follows section order
- **WHEN** the README is generated or updated following the guide
- **THEN** all mandatory sections are present in the specified order

### Requirement: Platform and Editor Support Info
The guide SHALL require a platform/editor support table with status indicators for each supported platform and editor.

#### Scenario: Platform support table
- **WHEN** a user reads the README
- **THEN** they see a table listing Linux (primary), macOS (supported), Windows (not supported), Zed (primary editor), VS Code (basic support), and Claude Code (integrated)

### Requirement: CLI Tool Documentation Coverage
The guide SHALL require that all user-facing `bin/set-*` commands are documented in the CLI Reference section.

#### Scenario: New CLI tool added
- **WHEN** a new `set-*` script is added to `bin/`
- **THEN** the guide's update checklist reminds the author to add it to the CLI Reference

### Requirement: Known Issues Section
The guide SHALL require a "Known Issues & Limitations" section documenting current platform quirks, editor-specific issues, and areas needing improvement.

#### Scenario: Known issues are visible
- **WHEN** a user reads the README
- **THEN** they find a Known Issues section with current limitations and workarounds

### Requirement: Tone and Style Rules
The guide SHALL define tone and style rules: English language, technical but accessible, concise sentences, consistent formatting with tables for reference data.

#### Scenario: Tone consistency
- **WHEN** a README section is written following the guide
- **THEN** it uses English, avoids jargon without explanation, and uses tables for structured data

### Requirement: Update Checklist
The guide SHALL include an update checklist that authors follow when modifying the README, ensuring no sections become stale.

#### Scenario: Feature addition triggers checklist
- **WHEN** a new feature is implemented
- **THEN** the update checklist reminds the author to update relevant README sections (CLI Reference, Features, Known Issues)

### Requirement: AI Generation Instructions
The guide SHALL be usable as instructions for AI-assisted README generation, containing enough detail for an LLM to produce a conforming README.

#### Scenario: AI regeneration
- **WHEN** an LLM is asked to regenerate the README using the guide
- **THEN** the output follows the mandatory section structure, includes all CLI tools, and matches the tone rules
