## MODIFIED Requirements

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

#### Scenario: MCP unhealthy — checkpoint triggered (unchanged)
- **WHEN** `setup_design_bridge()` succeeds (MCP is registered)
- **AND** `check_design_mcp_health()` returns non-zero
- **THEN** a checkpoint with type `mcp_auth` is triggered
- **AND** the orchestrator blocks in the approval polling loop
- **AND** after approval, `check_design_mcp_health()` is retried once
- **AND** if retry succeeds and `DESIGN_FILE_REF` is set, snapshot is fetched
- **AND** if retry fails, decomposition proceeds without design context (logged as warning)

#### Scenario: Replan cycle re-fetches snapshot
- **WHEN** `run_decomposition()` is called during a replan cycle
- **AND** a design snapshot cache exists from a previous cycle
- **THEN** `fetch_design_snapshot(force=true)` is called to refresh the snapshot
- **AND** the new snapshot overwrites the cached file
