## ADDED Requirements

### Requirement: Design snapshot extraction via MCP

The system SHALL extract a comprehensive design snapshot from the design MCP server during preflight, after the health check passes, by running a dedicated `run_claude` call with MCP config.

#### Scenario: Successful snapshot extraction
- **WHEN** `fetch_design_snapshot()` is called
- **AND** `DESIGN_MCP_CONFIG` is set and health check has passed
- **AND** `DESIGN_FILE_REF` contains a valid design file URL
- **THEN** a `run_claude` call is made with `--mcp-config` and a snapshot extraction prompt
- **AND** the LLM calls `get_metadata`, `get_variable_defs`, and `get_design_context` MCP tools
- **AND** the output is a structured markdown document

#### Scenario: Snapshot extraction without design file reference
- **WHEN** `fetch_design_snapshot()` is called
- **AND** `DESIGN_FILE_REF` is empty
- **THEN** the function returns 1 without making MCP calls
- **AND** logs "No design file reference — skipping snapshot"

#### Scenario: Snapshot extraction with screenshot descriptions
- **WHEN** the snapshot LLM receives screenshot data from `get_screenshot`
- **THEN** it converts visual information into textual layout descriptions in the snapshot markdown
- **AND** no binary image data is stored in the snapshot file

### Requirement: Snapshot structured markdown format

The snapshot output SHALL follow a structured markdown format with specific sections for design inventory, tokens, components, and layout information.

#### Scenario: Complete snapshot structure
- **WHEN** a snapshot is successfully extracted
- **THEN** the markdown file contains sections: Pages & Frames (table), Design Tokens (colors, typography, spacing, shadows), Component Hierarchy (per-frame trees), Layout Breakpoints (responsive variants), and Visual Descriptions (textual layout descriptions)

#### Scenario: Partial design data
- **WHEN** an MCP tool returns empty or partial data (e.g., no variables defined)
- **THEN** the corresponding section in the snapshot notes "No data available" rather than being omitted

### Requirement: Snapshot caching in state directory

The system SHALL cache the snapshot at `$STATE_DIR/design-snapshot.md`, scoped to the current orchestration run.

#### Scenario: Snapshot file created after successful fetch
- **WHEN** `fetch_design_snapshot()` completes successfully
- **THEN** the snapshot is written to `$STATE_DIR/design-snapshot.md`
- **AND** the function returns 0

#### Scenario: Cached snapshot exists on subsequent call
- **WHEN** `fetch_design_snapshot()` is called
- **AND** `$STATE_DIR/design-snapshot.md` already exists from the current run
- **THEN** the function skips re-fetching and returns 0
- **AND** logs "Using cached design snapshot"

#### Scenario: Replan forces re-fetch
- **WHEN** `fetch_design_snapshot()` is called with `force=true`
- **AND** a cached snapshot exists
- **THEN** the cached file is overwritten with a fresh snapshot

### Requirement: Snapshot timeout and failure handling

The snapshot fetch SHALL have a 120-second timeout and SHALL NOT block orchestration on failure.

#### Scenario: Snapshot fetch timeout
- **WHEN** the `run_claude` snapshot call exceeds 120 seconds
- **THEN** the function returns 1
- **AND** logs "Design snapshot fetch timed out"
- **AND** orchestration proceeds with generic design prompt section (fallback)

#### Scenario: MCP tool call failure during snapshot
- **WHEN** one or more MCP tool calls fail during the snapshot extraction
- **THEN** the snapshot LLM includes available data and notes failures
- **AND** the partial snapshot is still saved and used

#### Scenario: Complete snapshot failure
- **WHEN** the `run_claude` call itself fails (non-zero exit)
- **THEN** the function returns 1
- **AND** no snapshot file is created
- **AND** orchestration proceeds with generic design prompt section (fallback)
