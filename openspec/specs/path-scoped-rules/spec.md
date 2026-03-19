## ADDED Requirements

### Requirement: GUI rules scoped to GUI paths
The system SHALL provide `.claude/rules/gui/` directory containing GUI-specific rules that load ONLY when the user is working on files matching `gui/**` or `tests/gui/**` paths.

#### Scenario: Editing a GUI file loads dialog rules
- **WHEN** the user edits a file matching `gui/**/*.py`
- **THEN** the dialog rules (WindowStaysOnTopHint patterns, helper imports) SHALL be loaded into context

#### Scenario: Editing a non-GUI file does not load GUI rules
- **WHEN** the user edits a file matching `bin/set-*` or `lib/**`
- **THEN** no GUI-specific rules SHALL be loaded into context

### Requirement: GUI testing rules file
The system SHALL provide `.claude/rules/gui/testing.md` with YAML frontmatter `paths: ["gui/**", "tests/gui/**"]` containing the pytest command, test trigger words, test patterns reference, and the "do not run tests automatically" directive.

#### Scenario: Testing rules loaded when editing test files
- **WHEN** the user edits a file matching `tests/gui/**`
- **THEN** the testing rules (pytest command, fixture patterns, test file naming) SHALL be available in context

### Requirement: GUI dialogs rules file
The system SHALL provide `.claude/rules/gui/dialogs.md` with YAML frontmatter `paths: ["gui/**"]` containing the macOS Always-On-Top Dialog Rule with all three patterns (system dialogs via helpers, custom QDialogs with explicit flag, custom subclasses).

#### Scenario: Dialog rules loaded when creating GUI widgets
- **WHEN** the user edits a file matching `gui/**/*.py`
- **THEN** the dialog rules (WindowStaysOnTopHint, helper imports from `gui/dialogs/helpers.py`) SHALL be available in context

### Requirement: GUI debug and startup rules file
The system SHALL provide `.claude/rules/gui/debug-startup.md` with YAML frontmatter `paths: ["gui/**"]` containing the debug log location, rotation config, startup commands, and troubleshooting tips.

#### Scenario: Debug rules loaded when debugging GUI
- **WHEN** the user edits a file matching `gui/**/*.py`
- **THEN** the debug log location (`/tmp/set-control.log`) and startup commands SHALL be available in context

### Requirement: OpenSpec artifacts rules file
The system SHALL provide `.claude/rules/openspec-artifacts.md` with YAML frontmatter `paths: ["openspec/**"]` containing the "no project-specific content" rule for open-source artifact creation.

#### Scenario: OpenSpec rule loaded when writing artifacts
- **WHEN** the user edits or creates a file matching `openspec/**`
- **THEN** the rule about no client names, no absolute paths, and generic descriptions SHALL be available in context

#### Scenario: OpenSpec rule not loaded outside openspec/
- **WHEN** the user edits a file matching `gui/**` or `bin/**`
- **THEN** the OpenSpec artifacts rule SHALL NOT be loaded into context

### Requirement: README update rules file
The system SHALL provide `.claude/rules/readme-updates.md` with YAML frontmatter `paths: ["README.md", "docs/readme-guide.md"]` containing the README update procedure referencing `docs/readme-guide.md`.

#### Scenario: README rules loaded when editing README
- **WHEN** the user edits `README.md`
- **THEN** the README update procedure (read guide, check CLI completeness, follow section order) SHALL be available in context

### Requirement: Rules use YAML frontmatter for path scoping
Each rules file SHALL begin with YAML frontmatter containing a `paths` array of glob patterns. Files without frontmatter or without a `paths` field SHALL load unconditionally.

#### Scenario: Frontmatter format
- **WHEN** a rules file contains `paths: ["gui/**", "tests/gui/**"]` in its YAML frontmatter
- **THEN** the rule SHALL only load when the user is working on files matching those patterns
