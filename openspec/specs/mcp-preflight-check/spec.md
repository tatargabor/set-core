# Mcp Preflight Check Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Preflight gate before decomposition

The Python orchestrator SHALL run MCP health checks and snapshot fetch in `_fetch_design_context()` within `run_decomposition()`. When the health check passes and a design file reference is configured, the preflight SHALL fetch a design snapshot. This replaces the bash planner's inline preflight calls.

#### Scenario: MCP healthy with design file — snapshot fetched
- **WHEN** `_fetch_design_context()` detects a design MCP
- **AND** `design_file` is configured
- **AND** `setup_design_bridge` and `check_design_mcp_health` succeed via bash subprocess
- **THEN** `fetch_design_snapshot` is called via bash subprocess
- **AND** the resulting snapshot content is returned for injection into the decomposition prompt

#### Scenario: MCP healthy without design file — no snapshot
- **WHEN** `_fetch_design_context()` detects a design MCP
- **AND** `design_file` is NOT configured
- **THEN** no snapshot is fetched
- **AND** an empty string is returned (no design context injected)
- **AND** no error is raised

#### Scenario: MCP unhealthy — fail-fast
- **WHEN** `_fetch_design_context()` detects a design MCP
- **AND** `design_file` is configured
- **AND** `check_design_mcp_health` fails via bash subprocess
- **THEN** a `RuntimeError` is raised (unless `DESIGN_OPTIONAL=true`)
- **AND** the error message includes the MCP server name and suggests authentication

#### Scenario: No design MCP registered — skip preflight
- **WHEN** `_fetch_design_context()` finds no design MCP in settings
- **THEN** no health check or fetch is performed
- **AND** an empty string is returned

#### Scenario: Replan cycle re-fetches snapshot
- **WHEN** `run_decomposition()` is called during a replan cycle
- **AND** `replan_ctx` is provided
- **THEN** `_fetch_design_context(force=True)` is called
- **AND** the snapshot is re-fetched even if cached
