## ADDED Requirements

## IN SCOPE
- `design_source_path` directive for external design directory configuration
- External design directory mounting into worktrees via symlink
- Design token extraction from external repo's CSS custom properties
- Design rule injection from external repo's `.set-designer/design-rules/`
- Fallback to in-project `v0-export/` when external path not configured

## OUT OF SCOPE
- Git operations on the external design repo (pull, commit, branch)
- Multi-repo sync or conflict resolution
- Automatic design-to-component mapping
- Design token diffing between versions
- Figma/Penpot MCP server integration

### Requirement: External design directory mounting
The system SHALL mount an external design directory into worktrees when `design_source_path` is configured. The mount SHALL use an absolute symlink, identical to the existing v0-export symlink pattern.

#### Scenario: External design path configured and exists
- **WHEN** `design_source_path` is set to `~/projects/consumer-app-design` in orchestration config
- **AND** that directory exists
- **THEN** the dispatcher SHALL create a symlink `<wt>/v0-export → <resolved-path>`
- **AND** SHALL log the symlink creation at INFO level

#### Scenario: External design path configured but missing
- **WHEN** `design_source_path` is set but the directory does not exist
- **THEN** the system SHALL log a WARNING with the missing path
- **AND** SHALL fall back to in-project `v0-export/` detection
- **AND** SHALL NOT fail the dispatch

#### Scenario: No external path configured
- **WHEN** `design_source_path` is not set or None
- **THEN** the system SHALL use the existing in-project `v0-export/` detection logic unchanged

#### Scenario: Symlink already exists in worktree
- **WHEN** `<wt>/v0-export` already exists as a symlink
- **THEN** the system SHALL skip creation and return True

### Requirement: Design token extraction
The system SHALL extract CSS custom properties from the external design repo's `app/globals.css` and format them as a markdown section for agent consumption.

#### Scenario: Standard shadcn/ui globals.css
- **WHEN** `globals.css` contains `:root { --background: oklch(0.985 0 0); ... }` and `.dark { --background: oklch(0.178 0 0); ... }` blocks
- **THEN** the system SHALL extract all `--variable: value` pairs
- **AND** SHALL group them by light/dark theme
- **AND** SHALL return a markdown string with `## Design Tokens` header

#### Scenario: globals.css not found
- **WHEN** the external design directory does not contain `app/globals.css`
- **THEN** the system SHALL return an empty string
- **AND** SHALL log a debug message

#### Scenario: @theme block present
- **WHEN** `globals.css` contains `@theme { ... }` blocks (Tailwind 4 custom fonts, spacing)
- **THEN** the system SHALL extract those values and include in the token output

### Requirement: Design rule injection
The system SHALL inject design rules from the external repo's `.set-designer/design-rules/` directory into the worktree's `.claude/rules/` as symlinked files.

#### Scenario: Design rules directory exists
- **WHEN** the external design repo has `.set-designer/design-rules/` with `.md` files
- **THEN** the system SHALL symlink each file into `<wt>/.claude/rules/design-<filename>`
- **AND** SHALL log the number of design rules injected

#### Scenario: Design rules directory missing
- **WHEN** the external design repo has no `.set-designer/design-rules/`
- **THEN** the system SHALL skip rule injection silently (debug log only)

#### Scenario: Rule file name collision
- **WHEN** a design rule file name conflicts with an existing rule in `<wt>/.claude/rules/`
- **THEN** the system SHALL prefix with `design-` to avoid collision
- **AND** SHALL log a warning about the naming conflict
