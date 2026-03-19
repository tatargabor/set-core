## Why

When a design MCP (e.g., Figma) is registered in a project's settings.json, the orchestrator currently treats MCP failures as non-fatal — the planner silently falls back to markdown-based design docs. This means agents build UI without design tokens, components, or layout specs from the design tool, producing work that must be redone. The user explicitly requires: "if Figma is configured, no fallback allowed."

The orchestrator needs a preflight gate that validates MCP connectivity before decomposition, pausing for user intervention (authentication) when needed — using the existing checkpoint infrastructure.

## What Changes

- Add a preflight MCP health check phase before decomposition in the orchestrator
- When a design MCP is registered but not authenticated, trigger a checkpoint with type `mcp_auth` that blocks planning until the user authenticates
- The checkpoint appears in the web dashboard, TUI, and CLI — user authenticates via `/mcp` in Claude Code, then approves the checkpoint to continue
- The existing `checkpoint_auto_approve` directive does NOT auto-approve `mcp_auth` checkpoints (auth requires human action)
- Add a `whoami`-based probe to test MCP connectivity via `run_claude`

## Capabilities

### New Capabilities
- `mcp-preflight-check`: Pre-decomposition MCP health validation with checkpoint-based blocking when authentication is required

### Modified Capabilities
- `design-bridge`: Change non-fatal behavior to fail-fast when MCP is registered but unreachable, gated by checkpoint instead of silent fallback

## Impact

- `lib/orchestration/planner.sh` — new preflight function before decompose call
- `lib/orchestration/state.sh` — `mcp_auth` checkpoint type excluded from auto-approve
- `lib/design/bridge.sh` — new `check_design_mcp_health()` function
- `web/src/components/CheckpointBanner.tsx` — MCP-specific checkpoint message
- `lib/set_orch/api.py` — no changes needed (existing approve endpoint works)
