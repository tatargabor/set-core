## ADDED Requirements

### Requirement: Design MCP detection from project settings
The system SHALL detect registered design MCP servers by scanning `.claude/settings.json` for MCP server entries whose name matches known design tool patterns (figma, penpot, sketch, zeplin).

#### Scenario: Figma MCP detected
- **WHEN** `.claude/settings.json` contains an `mcpServers.figma` entry
- **THEN** `detect_design_mcp()` returns `"figma"`

#### Scenario: No design MCP registered
- **WHEN** `.claude/settings.json` has no MCP entries matching design tool patterns
- **THEN** `detect_design_mcp()` returns non-zero exit code

#### Scenario: Settings file missing
- **WHEN** `.claude/settings.json` does not exist
- **THEN** `detect_design_mcp()` returns non-zero exit code without error output

### Requirement: MCP config export for run_claude passthrough
The system SHALL extract a design MCP server's config from `.claude/settings.json` and write it to a temporary JSON file compatible with `claude --mcp-config`.

#### Scenario: Config export for Figma
- **WHEN** `get_design_mcp_config "figma"` is called
- **THEN** a temp JSON file is created containing `{"mcpServers":{"figma":{...}}}` with the full server config from settings.json
- **AND** the file path is printed to stdout

### Requirement: Design prompt section generation
The system SHALL generate a prompt section that instructs LLMs to use design MCP tools when available. When a cached design snapshot exists, the prompt section SHALL include the full snapshot content instead of generic instructions.

#### Scenario: Prompt with cached design snapshot
- **WHEN** `design_prompt_section "figma"` is called
- **AND** `$STATE_DIR/design-snapshot.md` exists and is non-empty
- **THEN** the output includes the full snapshot content prefixed with a "Design Context (Snapshot)" header
- **AND** a note that the design MCP is also available for live queries during implementation

#### Scenario: Prompt without snapshot (fallback to generic)
- **WHEN** `design_prompt_section "figma"` is called
- **AND** no cached snapshot exists at `$STATE_DIR/design-snapshot.md`
- **THEN** the output includes generic design tool capabilities and query instructions (existing behavior)

#### Scenario: Prompt with design file reference
- **WHEN** `design_prompt_section "figma"` is called and `DESIGN_FILE_REF` is set
- **AND** no cached snapshot exists
- **THEN** the output includes design tool name, available query types (frames, components, tokens, layout), the file reference, and instructions to flag missing frames as ambiguities

### Requirement: Design file reference from orchestration config
The system SHALL read the `design_file` field from `.claude/orchestration.yaml` as the design file reference for prompt sections.

#### Scenario: Design file configured
- **WHEN** `.claude/orchestration.yaml` contains `design_file: "https://figma.com/file/XYZ"`
- **THEN** the bridge uses this URL as `DESIGN_FILE_REF` in prompt sections and proposal injections

#### Scenario: No design file configured
- **WHEN** `.claude/orchestration.yaml` has no `design_file` field
- **THEN** the bridge functions without a file reference — design MCP is still available for querying but no specific file is pre-referenced

### Requirement: Non-fatal design bridge
All design-bridge functions SHALL be non-fatal during agent execution. However, during orchestrator preflight, MCP availability SHALL be validated and failures SHALL trigger a checkpoint instead of silent fallback.

#### Scenario: MCP unreachable during planner run
- **WHEN** the design MCP server is registered but unreachable
- **AND** the orchestrator preflight has already been approved or skipped
- **THEN** the planner completes normally — design prompt section was injected but MCP tool calls return errors, which the LLM handles gracefully

#### Scenario: MCP unreachable during agent execution
- **WHEN** the design MCP server is registered but unreachable during Ralph loop iteration
- **THEN** the agent handles MCP errors gracefully and continues implementation using available context

#### Scenario: MCP unreachable during orchestrator preflight
- **WHEN** the design MCP server is registered but not authenticated
- **AND** the orchestrator is in preflight phase before decomposition
- **THEN** a checkpoint of type `mcp_auth` is triggered instead of silently continuing

### Requirement: Design MCP health check function
The bridge SHALL provide a `check_design_mcp_health()` function that tests MCP connectivity using a lightweight `run_claude` probe.

#### Scenario: Health check with authenticated MCP
- **WHEN** `check_design_mcp_health()` is called
- **AND** `DESIGN_MCP_CONFIG` is set to a valid config file
- **THEN** the function runs `run_claude` with a probe prompt and the MCP config
- **AND** returns 0 if the MCP responds successfully

#### Scenario: Health check without MCP config
- **WHEN** `check_design_mcp_health()` is called
- **AND** `DESIGN_MCP_CONFIG` is not set
- **THEN** the function returns 1 without running a probe

### Requirement: Agent rule template for design-aware implementation
The system SHALL provide a deployable rule template (`templates/rules/design-bridge-rule.md`) that instructs agents to query the design MCP tool when implementing UI elements.

#### Scenario: Rule deployed to project with design MCP
- **WHEN** `wt-project init` runs on a project with a registered design MCP
- **THEN** the design-bridge rule is deployed to `.claude/rules/wt-design-bridge.md`

#### Scenario: Rule not deployed without design MCP
- **WHEN** `wt-project init` runs on a project without a design MCP
- **THEN** no design-bridge rule is deployed
