# Proposal: figma-direct-fetch

## Problem

The current Figma design fetching (`scripts/fetch-figma-design.py`) spawns 4 separate Claude subprocess calls to interact with the Figma MCP — each with a 20-minute timeout, LLM token costs, and non-deterministic behavior. Two real session logs show the same MCP producing radically different outputs 4 seconds apart: one got 13 frames with full Tailwind tokens, the other got 3 frames in prose format. The agent "decides" what to do at runtime, making the pipeline unreliable.

Additionally, the design fetch happens during orchestration preflight (every run), even though designs rarely change. This wastes time and money on every orchestration run.

## Solution

1. **New `wt-figma-fetch` command**: A standalone CLI tool that fetches design data via direct MCP protocol calls (Python `mcp` SDK) — no Claude subprocess, no LLM, no non-determinism. Saves raw MCP responses plus an assembled `design-snapshot.md` into a target directory alongside existing docs. The output is committed to git as a persistent artifact.

2. **Disable runtime fetch in orchestration**: The planner/dispatcher/verifier already read committed `design-snapshot.md` files. Disable the preflight fetch step so orchestration uses the committed snapshot directly. Keep the existing bridge.sh code for reading/filtering snapshots — only disable the fetch trigger.

## Scope

### In scope
- `bin/wt-figma-fetch` command using Python `mcp` SDK for direct MCP calls
- Support both Design files and Make files (different fetch strategies)
- Raw response preservation (every MCP response saved as-is)
- Assembled `design-snapshot.md` in the same format the pipeline already expects
- Auto-discovery of `design_file:` references from `orchestration.yaml` / project docs
- Disable preflight fetch in `planner.py` (flag or config-based)

### Out of scope
- OAuth token refresh logic (token valid until 2026-08, refresh manually when needed)
- Changes to how planner/dispatcher/verifier read the snapshot (they already work)
- MCP server installation or auth setup (uses existing Claude Code OAuth)

## Key decisions

- **Direct MCP over Claude subprocess**: The `mcp` Python SDK (v1.26.0) is installed, Figma MCP uses HTTP transport at `https://mcp.figma.com/mcp`. Direct calls take ~3-5 seconds vs 4×20min timeout windows.
- **Raw + assembled output**: Raw MCP responses saved alongside the assembled snapshot so future processing changes don't require re-fetching.
- **Make file strategy**: `get_metadata` → type detection → `get_design_context` + `read_resource` for source files → parse Tailwind classes into tokens. Based on session log analysis showing this produces 13 frames with full token coverage.
- **Committed artifact**: Design snapshot is a git-tracked file, not a runtime cache. Only re-fetched when the design actually changes.
- **wt default Python**: Uses set-core' standard Python (miniconda/linuxbrew — whatever is the wt default), with `mcp` SDK as dependency.
