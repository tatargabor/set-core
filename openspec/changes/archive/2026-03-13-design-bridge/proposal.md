## Why

The orchestration pipeline (planner, decompose, dispatcher, agent runtime, verifier) has no awareness of external design tools. When a project has a Figma file with frames, design tokens, and component specs, agents implement UI by guessing — resulting in inconsistent colors, wrong spacing, and missing states. The Figma MCP server (official, 13 tools) and `claude -p --mcp-config` flag make it possible to give every stage of the pipeline access to design context, but there is no abstraction layer to detect, configure, and inject this capability.

## What Changes

- Introduce a design-bridge abstraction in `lib/design/` that detects registered design MCP servers, exports their config for `run_claude --mcp-config`, and generates prompt enrichment sections
- Extend `run_claude()` in `wt-common.sh` to accept `--mcp-config` passthrough when design MCP is available
- Inject design context at every pipeline stage: decompose skill gets frame/component awareness, planner gets `--mcp-config`, dispatcher writes design references into `proposal.md`, agent runtime rule tells agents to query design MCP, verifier can optionally check design compliance
- The bridge is tool-agnostic — it detects any registered design MCP (figma, penpot, etc). Concrete adapters (Figma token, file ID) live in project templates (`set-project-web`), not here
- Ambiguity handling: when a required frame/page is missing from the design tool, the system surfaces it as an ambiguity for user resolution

## Capabilities

### New Capabilities
- `design-bridge`: Detection of design MCP servers, config export for `--mcp-config`, prompt enrichment for all pipeline stages, design reference injection into proposals, ambiguity surfacing for missing design elements

### Modified Capabilities
- `orchestration-engine`: Planner and dispatcher gain design-aware prompt sections and `--mcp-config` passthrough when design MCP is detected
- `decomposition-skill`: Decompose queries design MCP for frame/component inventory during change scoping

## Impact

- **lib/design/bridge.sh** — New module: `detect_design_mcp()`, `get_design_mcp_config()`, `design_prompt_section()`
- **bin/wt-common.sh** — `run_claude()` extended with optional `--mcp-config` passthrough
- **lib/orchestration/planner.sh** — Sources design bridge, adds `--mcp-config` to `run_claude` calls, injects design prompt section
- **lib/orchestration/dispatcher.sh** — Writes design references into proposal.md per-change
- **.claude/skills/wt/decompose/SKILL.md** — Instructions to query design MCP for frame inventory
- **templates/rules/design-bridge-rule.md** — Agent rule deployed to projects with design MCP: "query design tool for UI implementation details"
- No breaking changes — projects without design MCP behave identically to today
