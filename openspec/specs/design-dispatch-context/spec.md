# Spec: Design Dispatch Context (delta)

## MODIFIED Requirements

### Requirement: Alias externalization
The `_DESIGN_BRIEF_ALIASES` hardcoded array in bridge.sh SHALL be emptied. Project-specific aliases SHALL be stored in per-scaffold files and loaded via the existing `DESIGN_BRIEF_ALIASES_FILE` environment variable.

The alias file format remains the same: one entry per line, `PageName:alias1,alias2,alias3`.

#### Scenario: No alias file configured
- **WHEN** `DESIGN_BRIEF_ALIASES_FILE` is empty or unset and `_DESIGN_BRIEF_ALIASES` is empty
- **THEN** the alias matching layer is skipped (no aliases to check) and only exact + stem layers are active

#### Scenario: Scaffold alias file deployed
- **WHEN** `DESIGN_BRIEF_ALIASES_FILE` points to a valid file with alias entries
- **THEN** those aliases are loaded and used for the alias matching layer

#### Scenario: Runner deploys alias file
- **WHEN** a scaffold directory contains `docs/design-brief-aliases.txt`
- **THEN** the runner script copies it to the test project and sets `DESIGN_BRIEF_ALIASES_FILE` in the orchestration config
