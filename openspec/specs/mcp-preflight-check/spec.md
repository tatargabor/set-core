## ADDED Requirements

### Requirement: MCP health probe via run_claude

The system SHALL validate design MCP connectivity by running a lightweight `run_claude` call with the MCP config before decomposition.

#### Scenario: Figma MCP authenticated and healthy
- **WHEN** `check_design_mcp_health()` is called with a valid MCP config
- **AND** the MCP server responds successfully to identity/tool queries
- **THEN** the function returns 0 (success)
- **AND** logs "Design MCP health check passed: <server_name>"

#### Scenario: Figma MCP not authenticated
- **WHEN** `check_design_mcp_health()` is called with a valid MCP config
- **AND** the MCP server returns authentication errors
- **THEN** the function returns 1 (failure)
- **AND** logs "Design MCP not authenticated: <server_name>"

#### Scenario: MCP probe timeout
- **WHEN** `check_design_mcp_health()` is called
- **AND** the `run_claude` call does not complete within 30 seconds
- **THEN** the function returns 1 (failure)
- **AND** logs "Design MCP health check timed out"

### Requirement: Preflight gate before decomposition

The orchestrator SHALL run MCP health checks after bridge setup but before the LLM decompose call in `run_decomposition()`. When the health check passes and a design file reference is configured, the preflight SHALL also fetch a design snapshot.

#### Scenario: MCP healthy with design file — snapshot fetched
- **WHEN** `setup_design_bridge()` succeeds
- **AND** `check_design_mcp_health()` returns 0
- **AND** `DESIGN_FILE_REF` is set
- **THEN** `fetch_design_snapshot()` is called to extract full design content
- **AND** if snapshot succeeds, `design_prompt_section()` returns snapshot content
- **AND** if snapshot fails, `design_prompt_section()` returns generic instructions (fallback)
- **AND** decomposition proceeds in either case

#### Scenario: MCP healthy without design file — no snapshot
- **WHEN** `setup_design_bridge()` succeeds
- **AND** `check_design_mcp_health()` returns 0
- **AND** `DESIGN_FILE_REF` is empty
- **THEN** no snapshot is fetched
- **AND** decomposition proceeds with generic design prompt section

#### Scenario: MCP unhealthy — checkpoint triggered
- **WHEN** `setup_design_bridge()` succeeds (MCP is registered)
- **AND** `check_design_mcp_health()` returns non-zero
- **THEN** a checkpoint with type `mcp_auth` is triggered
- **AND** the orchestrator blocks in the approval polling loop
- **AND** after approval, `check_design_mcp_health()` is retried once
- **AND** if retry succeeds and `DESIGN_FILE_REF` is set, snapshot is fetched
- **AND** if retry fails, decomposition proceeds without design context (logged as warning)

#### Scenario: No design MCP registered — skip preflight
- **WHEN** `setup_design_bridge()` returns non-zero (no MCP detected)
- **THEN** no health check is performed
- **AND** decomposition proceeds without design context

#### Scenario: Replan cycle re-fetches snapshot
- **WHEN** `run_decomposition()` is called during a replan cycle
- **AND** a design snapshot cache exists from a previous cycle
- **THEN** `fetch_design_snapshot(force=true)` is called to refresh the snapshot
- **AND** the new snapshot overwrites the cached file

### Requirement: mcp_auth checkpoint excluded from auto-approve

The `mcp_auth` checkpoint type SHALL NOT be auto-approved by the `checkpoint_auto_approve` config directive, because MCP authentication requires human browser interaction.

#### Scenario: Auto-approve enabled with mcp_auth checkpoint
- **WHEN** `checkpoint_auto_approve` is `true`
- **AND** a checkpoint of type `mcp_auth` is triggered
- **THEN** the checkpoint is NOT auto-approved
- **AND** the orchestrator blocks in the approval polling loop

#### Scenario: Auto-approve enabled with periodic checkpoint
- **WHEN** `checkpoint_auto_approve` is `true`
- **AND** a checkpoint of type `periodic` is triggered
- **THEN** the checkpoint IS auto-approved (existing behavior unchanged)

### Requirement: Checkpoint message includes authentication instructions

The `mcp_auth` checkpoint SHALL include actionable instructions in its notification and web dashboard display.

#### Scenario: Checkpoint notification content
- **WHEN** an `mcp_auth` checkpoint is triggered
- **THEN** the notification message includes the MCP server name and instructions: "Run /mcp → <server_name> → Authenticate in Claude Code, then run 'wt-orchestrate approve'"

#### Scenario: Web dashboard checkpoint banner
- **WHEN** the orchestration state has status `checkpoint` with type `mcp_auth`
- **THEN** the `CheckpointBanner` component displays the MCP-specific message with the server name and authentication instructions
