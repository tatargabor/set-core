## Why

The MCP preflight gate validates design tool authentication, but the decompose LLM receives only generic instructions ("you can query the design tool"). In practice, the LLM never queries Figma during decomposition — it has 40+ changes to plan and no motivation to make additional MCP calls. The design file content must be pre-fetched and injected as concrete context, not left as an optional runtime query.

## What Changes

- Extend the preflight phase with a **design snapshot fetch** after the health check passes — a `run_claude` call with MCP config that extracts the full design structure (pages, frames, components, tokens, layout info) into a structured markdown file
- Cache the snapshot at `$STATE_DIR/design-snapshot.md` (per-orchestration-run, not in git)
- Replace the generic `design_prompt_section()` output with the actual snapshot content when available — the decompose prompt receives concrete frame inventories, token values, and component hierarchies instead of "you can query Figma"
- Replan cycles re-fetch the snapshot (design may have changed between cycles)
- The snapshot `run_claude` call uses `get_metadata`, `get_variable_defs`, `get_design_context`, and optionally `get_screenshot` to extract and describe the design comprehensively

## Capabilities

### New Capabilities
- `design-snapshot`: Pre-fetching full design content from MCP during preflight, caching as structured markdown, and injecting as concrete context into decompose/replan prompts

### Modified Capabilities
- `design-bridge`: `design_prompt_section()` gains a snapshot-aware mode that returns cached design content instead of generic instructions when a snapshot exists
- `mcp-preflight-check`: Preflight flow extended with a snapshot phase after health check passes

## Impact

- **lib/design/bridge.sh** — New `fetch_design_snapshot()` function; `design_prompt_section()` modified to prefer snapshot content when `$STATE_DIR/design-snapshot.md` exists
- **lib/orchestration/planner.sh** — Preflight section calls `fetch_design_snapshot()` after health check; snapshot path passed to prompt builder
- **$STATE_DIR/design-snapshot.md** — New cached artifact per orchestration run (not committed to git)
- No breaking changes — projects without design MCP or design_file behave identically
