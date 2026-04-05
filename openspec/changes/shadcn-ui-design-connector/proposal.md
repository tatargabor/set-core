# Proposal: shadcn/ui Design Connector

## Why

The current design pipeline requires a Figma MCP server to generate design-snapshot.md. For Tailwind-based projects using shadcn/ui, the design tokens (colors, spacing, typography, radius) already live in the project's filesystem — in `tailwind.config.ts`, `globals.css` CSS variables, and `components.json`. A local filesystem-based connector can extract these tokens without any external tool dependency, producing the same design-snapshot.md format the pipeline already consumes. This makes the design pipeline accessible to projects that don't use Figma, and keeps tokens inherently in sync with the actual codebase.

## What Changes

- **New connector type**: A Python-based parser that reads shadcn/ui project files (`components.json`, `tailwind.config.ts`/`.js`, `globals.css`) and generates a `design-snapshot.md` in the same format as the Figma fetcher
- **Bridge detection expansion**: `detect_design_mcp()` currently only checks for registered MCP servers (figma/penpot/sketch/zeplin). A new detection path checks for local `components.json` as a shadcn/ui signal — no MCP required
- **Component catalog extraction**: Scan `src/components/ui/` to build a component inventory (which shadcn components are installed, their variants/props)
- **Preflight integration**: The planner preflight can generate a design snapshot from local files when no design MCP is detected but shadcn/ui is present
- **E2E scaffold update**: Add shadcn/ui configuration to an E2E scaffold (micro-web-shadcn variant) for testing the connector end-to-end

## Capabilities

### New Capabilities
- `shadcn-design-parser` — Parser that extracts design tokens from shadcn/ui project files (tailwind config, CSS variables, component catalog)
- `shadcn-design-detection` — Detection logic to identify shadcn/ui projects and trigger local snapshot generation

### Modified Capabilities
- `design-snapshot` — Extend snapshot generation to support local filesystem source (not just MCP fetch)
- `design-dispatch-context` — Ensure dispatch context fallback chain includes shadcn-generated snapshots

## Impact

- **Core (`lib/design/`)**: New `shadcn_parser.py` alongside existing `fetcher.py` and `design_parser.py`
- **Bridge (`lib/design/bridge.sh`)**: `detect_design_mcp()` gains a fallback path for local shadcn detection; new `detect_shadcn_project()` function
- **Planner (`lib/set_orch/planner.py`)**: `_fetch_design_context()` gains a shadcn path when MCP is absent
- **Web module (`modules/web/`)**: Framework detection may contribute shadcn awareness
- **E2E scaffolds**: New or modified scaffold with shadcn/ui configuration for connector validation
- **No breaking changes**: Projects without shadcn/ui are unaffected; Figma MCP path unchanged
