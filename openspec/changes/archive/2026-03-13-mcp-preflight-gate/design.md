## Context

The orchestrator currently has a design bridge (`lib/design/bridge.sh`) that detects registered design MCP servers and passes their config to `run_claude()`. All bridge functions are non-fatal — if MCP detection or connectivity fails, the pipeline continues without design context.

The checkpoint system (`lib/orchestration/state.sh`) already supports multiple checkpoint types (`periodic`, `token_hard_limit`, `failure`, `completion`) with a polling loop, web API approval, and auto-approve option.

The gap: there is no validation that a registered MCP is actually usable (authenticated) before decomposition begins. The planner injects design context into the prompt, but if the MCP returns auth errors, the LLM silently falls back to markdown specs.

## Goals / Non-Goals

**Goals:**
- Validate MCP health before decomposition, using the existing checkpoint mechanism
- Block planning when design MCP is registered but not authenticated
- Surface the blocker in web dashboard, TUI, and CLI with actionable instructions
- Allow user to authenticate and resume without restarting the orchestrator

**Non-Goals:**
- Automatic MCP authentication (OAuth requires browser interaction)
- Supporting MCP health checks for non-design MCPs (future extension)
- Changing the bridge behavior during agent execution (agents still get non-fatal MCP)

## Decisions

### D1: Probe mechanism — `run_claude` with `whoami` prompt

Use a lightweight `run_claude` call with the MCP config to test connectivity. The probe prompt asks the LLM to call the design tool's identity endpoint (e.g., Figma `whoami`).

**Why not direct HTTP probe:** The MCP may use stdio transport (not HTTP), and auth tokens are managed by Claude Code's MCP layer — we can't replicate that outside `claude`.

**Why not `claude mcp list`:** That only shows registered servers, not whether they're authenticated.

**Implementation:** A 30-second timeout `run_claude` call with the design MCP config. Parse output for success indicators ("authenticated", user name) vs failure indicators ("needs authentication", "unauthorized", "error").

### D2: Checkpoint type — `mcp_auth` excluded from auto-approve

The `mcp_auth` checkpoint type requires human action (OAuth in browser). The `checkpoint_auto_approve` config directive MUST NOT apply to it.

**Why:** Auto-approve is for unattended E2E runs where periodic checkpoints should not block. But MCP auth physically cannot be automated — auto-approving it would just let the planner run without design data, which is the exact problem we're solving.

### D3: Placement — between config parse and decompose, in planner.sh

The preflight runs inside `run_decomposition()` in `planner.sh`, after `setup_design_bridge()` succeeds but before the LLM decompose call. This is the narrowest insertion point.

**Alternatives considered:**
- In `set-orchestrate start` before calling planner: too early, bridge not yet set up
- As a separate orchestrator phase: over-engineered for a single check
- In `bridge.sh` itself: wrong layer — bridge is a library, checkpoints are orchestrator concerns

### D4: Dashboard message — actionable instructions

The `CheckpointBanner.tsx` component shows checkpoint-type-specific messages. For `mcp_auth`:
```
"Figma MCP needs authentication. Run /mcp → figma → Authenticate in Claude Code, then approve."
```

## Risks / Trade-offs

- **[Risk] Probe timeout slows start** → 30s timeout is acceptable for a one-time pre-flight check. If MCP is healthy, probe completes in ~5s.
- **[Risk] Probe flaky on slow networks** → Single retry with backoff. If both fail, checkpoint is triggered — user can approve manually if they know MCP works.
- **[Risk] Non-Figma MCPs may not have `whoami`** → Probe uses a generic "identify yourself" prompt. If the MCP doesn't support identity queries, the probe checks for any successful tool call vs auth error. Worst case: probe times out and checkpoint is triggered (safe default).

## Migration Plan

1. Add `check_design_mcp_health()` to `bridge.sh`
2. Add `mcp_auth` exclusion to `trigger_checkpoint()` auto-approve logic in `state.sh`
3. Insert preflight call in `planner.sh` `run_decomposition()`
4. Add checkpoint type message to `CheckpointBanner.tsx`
5. No config changes needed — works automatically when design MCP is registered

**Rollback:** Remove the preflight call from `planner.sh`. Everything else is additive.

## Open Questions

None — all decisions are resolved.
