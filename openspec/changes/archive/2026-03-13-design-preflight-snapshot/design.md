## Context

The design-bridge and mcp-preflight-check capabilities already exist. The bridge detects design MCP servers, exports config, generates generic prompt sections. The preflight gate runs a 30-second `whoami` probe and triggers `mcp_auth` checkpoint on failure. The decompose LLM receives `--mcp-config` and generic instructions to "query the design tool if needed."

Problem: the decompose LLM never uses the MCP during planning. It has dozens of changes to scope and no incentive to make additional API calls. The design context must be pre-materialized.

## Goals / Non-Goals

**Goals:**
- Pre-fetch full design content during preflight (after health check passes)
- Cache as structured markdown in the orchestration state directory
- Inject cached content directly into decompose/replan prompts
- Support re-fetch on replan cycles (design may change between cycles)

**Non-Goals:**
- Per-frame screenshot export to disk (text descriptions suffice for planning)
- Modifying the agent runtime design-bridge rule (agents still query MCP live during implementation)
- Supporting non-MCP design tools (manual design docs remain a separate concern)

## Decisions

### D1: Snapshot extraction via run_claude with MCP

The snapshot is extracted by a dedicated `run_claude` call with `--mcp-config`, not by direct API calls.

**Why**: Design MCP tools use stdio/HTTP transport managed by Claude Code's MCP layer. We cannot call them directly from bash. The existing `run_claude` + `--mcp-config` pattern is proven (preflight health check uses it).

**Alternative**: Parse Figma REST API directly with curl + access token. Rejected — would bypass MCP abstraction, require managing auth tokens separately, and break tool-agnosticism (Figma-only).

### D2: Three-tool extraction strategy

The snapshot LLM calls these Figma MCP tools in order:
1. `get_metadata(design_file_url)` — page/frame structure, dimensions, layer hierarchy
2. `get_variable_defs(design_file_url)` — design tokens (colors, typography, spacing)
3. `get_design_context(design_file_url)` — component structure in framework-oriented format

Optionally: `get_screenshot` for key frames, described textually in the snapshot markdown.

**Why**: This combination covers structure (what exists), tokens (how it looks), and components (how to build it). Each tool serves a distinct purpose. The `get_screenshot` output is processed by the snapshot LLM (which is multimodal) and converted to textual layout descriptions.

**Alternative**: Single `get_design_context` call. Rejected — misses design tokens and doesn't provide the structural overview needed for change scoping.

### D3: Cache location at $STATE_DIR/design-snapshot.md

The snapshot is stored in the orchestration state directory (same level as `orchestration-state.json`), not in git.

**Why**: The snapshot is a runtime artifact tied to a specific orchestration run. It should not pollute the repository. The state directory is already gitignored and cleaned between runs.

**Alternative**: `.claude/design-cache.md` in the project. Rejected — could end up in git, would persist across unrelated orchestration runs with stale data.

### D4: Snapshot prompt produces structured markdown

The `run_claude` call receives a prompt that instructs it to compile MCP tool outputs into a specific markdown structure:
- `## Pages & Frames` — inventory table (page, frame, dimensions, type)
- `## Design Tokens` — colors, typography, spacing, shadows subsections
- `## Component Hierarchy` — per-frame component trees with properties
- `## Layout Breakpoints` — responsive breakpoints and frame variants
- `## Visual Descriptions` — text descriptions of key frame screenshots (if captured)

**Why**: Structured markdown is directly injectable into the decompose prompt. The decompose LLM can reference specific frames by name and map changes to design elements.

### D5: Timeout and failure handling

- Snapshot fetch timeout: 120 seconds (longer than health check, as it makes multiple MCP calls)
- On timeout/failure: log warning, proceed with generic `design_prompt_section()` fallback (current behavior)
- NOT a checkpoint — the design is already authenticated (health check passed). Snapshot failure is likely rate-limiting or transient.

**Why**: The snapshot is valuable but not blocking. If it fails, the system falls back to the existing generic prompt — same behavior as today. A hard block would be too aggressive for what is essentially a quality enhancement.

**Alternative**: Trigger checkpoint on snapshot failure. Rejected — health check already validated auth. Snapshot failure is a different class of problem (rate limit, large file, timeout) that doesn't benefit from human intervention.

### D6: Replan re-fetches snapshot

When `run_decomposition()` is called during a replan cycle, the snapshot is re-fetched (overwriting the cached file). The cache is not shared across replan cycles.

**Why**: The design may have been updated between orchestration cycles. Stale design context leads to the same problem we're solving. Re-fetching is cheap (one LLM call) compared to running a full decomposition with wrong design data.

## Risks / Trade-offs

- [Rate limits] Figma MCP has per-minute rate limits on paid plans, 6 calls/month on free. The snapshot makes 3-4 MCP tool calls per fetch. → Mitigation: Only fetch during preflight/replan, not per-change. Document rate limit consideration.
- [Large files] A complex design file could produce a very large snapshot that bloats the decompose prompt. → Mitigation: The snapshot prompt instructs the LLM to summarize and limit output to key structures (max ~50 components, top-level frames only for deeply nested files).
- [Snapshot staleness] Between snapshot and change implementation, the design could change. → Mitigation: Agents still have live MCP access during implementation (design-bridge rule). The snapshot is for planning accuracy, not implementation precision.
- [MCP tool naming] Figma MCP tool names may change in future versions. → Mitigation: The snapshot prompt references tools by purpose, not hardcoded names. The LLM adapts to available tools.
