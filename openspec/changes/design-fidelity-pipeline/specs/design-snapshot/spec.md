## MODIFIED Requirements

### Requirement: Snapshot caching in state directory

The system SHALL cache the snapshot at `$DESIGN_SNAPSHOT_DIR/design-snapshot.md` (typically project root for spec-mode orchestration), scoped to the current orchestration run. The snapshot SHALL also be accessible to dispatched agents via the project root copy.

#### Scenario: Snapshot file created after successful fetch
- **WHEN** `fetch_design_snapshot()` completes successfully
- **THEN** the snapshot is written to `$DESIGN_SNAPSHOT_DIR/design-snapshot.md`
- **AND** if `$DESIGN_SNAPSHOT_DIR` differs from the project root, a copy is placed at `$PROJECT_ROOT/design-snapshot.md`
- **AND** the function returns 0

#### Scenario: Cached snapshot exists on subsequent call
- **WHEN** `fetch_design_snapshot()` is called
- **AND** `$DESIGN_SNAPSHOT_DIR/design-snapshot.md` already exists from the current run
- **THEN** the function skips re-fetching and returns 0
- **AND** logs "Using cached design snapshot"

#### Scenario: Replan forces re-fetch
- **WHEN** `fetch_design_snapshot()` is called with `force=true`
- **AND** a cached snapshot exists
- **THEN** the cached file is overwritten with a fresh snapshot

### Requirement: Design prompt section generation

The system SHALL generate a prompt section that instructs LLMs to use design MCP tools when available. When a cached design snapshot exists, the prompt section SHALL include the full snapshot content instead of generic instructions. The prompt section SHALL explicitly instruct the planner to embed design token values and frame references in change scope descriptions.

#### Scenario: Prompt with cached design snapshot
- **WHEN** `design_prompt_section "figma"` is called
- **AND** `$DESIGN_SNAPSHOT_DIR/design-snapshot.md` exists and is non-empty
- **THEN** the output includes the full snapshot content prefixed with a "Design Context (Snapshot)" header
- **AND** instructions to embed specific design tokens and frame references in each change scope that involves UI work
- **AND** a note that the design MCP is also available for live queries during implementation

#### Scenario: Prompt without snapshot (fallback to generic)
- **WHEN** `design_prompt_section "figma"` is called
- **AND** no cached snapshot exists
- **THEN** the output includes generic design tool capabilities and query instructions
