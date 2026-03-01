## ADDED Requirements

### Requirement: install.sh detects legacy inline hooks and warns
When `install.sh` runs and detects legacy inline hooks in `.claude/skills/openspec-*/SKILL.md` files (via `wt-memory-hooks check`), it SHALL print a warning with instructions to run `wt-memory-hooks remove` and a link to MIGRATION.md. The warning SHALL NOT block installation.

#### Scenario: Legacy hooks detected during install
- **WHEN** user runs `bash install.sh` and legacy inline hooks exist in SKILL.md files
- **THEN** install completes successfully but prints a yellow warning: "Legacy inline memory hooks detected. Run 'wt-memory-hooks remove' to clean up. See MIGRATION.md for details."

#### Scenario: No legacy hooks present
- **WHEN** user runs `bash install.sh` and no legacy inline hooks exist
- **THEN** install completes without any legacy hook warning

### Requirement: Deprecated specs have sunset timeline
The `memory-hooks-cli` and `memory-hooks-gui` specs SHALL include a sunset notice stating that `wt-memory-hooks install` and GUI hook actions will be removed in the next release after this one. The `check` and `remove` subcommands SHALL be documented as retained for cleanup purposes.

#### Scenario: memory-hooks-cli sunset notice
- **WHEN** a developer reads `openspec/specs/memory-hooks-cli/spec.md`
- **THEN** they see a sunset notice: "The `install` subcommand will be removed in the next release. `check` and `remove` are retained for legacy cleanup."

#### Scenario: memory-hooks-gui sunset notice
- **WHEN** a developer reads `openspec/specs/memory-hooks-gui/spec.md`
- **THEN** they see a sunset notice with the same timeline as memory-hooks-cli

### Requirement: README date and sections are current
The README.md "Latest update" date SHALL reflect the current release date. All sections SHALL be consistent with the hook-driven memory architecture (no references to `wt-memory-hooks install` as an active workflow).

#### Scenario: README date is current
- **WHEN** a user reads the README
- **THEN** the "Latest update" date matches the release date

#### Scenario: README memory section is consistent
- **WHEN** a user reads the Developer Memory section
- **THEN** it describes hook-driven memory via shodh-memory and does not reference `wt-memory-hooks install` as an active step
