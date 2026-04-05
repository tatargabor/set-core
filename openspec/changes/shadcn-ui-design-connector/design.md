# Design: shadcn/ui Design Connector

## Context

The design pipeline currently has one primary path: Figma MCP → fetcher.py → design-snapshot.md. Projects using shadcn/ui with Tailwind CSS already have their design tokens locally — in `tailwind.config.ts`, CSS custom properties in `globals.css`, and a component registry in `components.json`. Adding a local parser avoids external tool dependency and keeps tokens in sync with the codebase.

### Current state
- `lib/design/fetcher.py` — async MCP client for Figma (OAuth, HTTP transport)
- `lib/design/design_parser.py` — `MakeParser` for .make files, `PassthroughParser` for pre-built .md
- `lib/design/bridge.sh` — bash functions consumed by planner, dispatcher, verifier
- Snapshot format: markdown with `## Design Tokens`, `## Component Hierarchy`, `## Source Files` sections

### Constraints
- Must produce identical snapshot format (bridge.sh parses specific section headers)
- Must not break existing Figma MCP path
- Core-only change (`lib/design/`) — no module-specific logic needed
- Parser must handle both Tailwind v3 (JS config) and v4 (CSS `@theme`)

## Goals / Non-Goals

**Goals:**
- Local design token extraction from shadcn/ui projects without external tools
- Same snapshot format so all downstream consumers work unchanged
- Automatic detection + generation during planner preflight

**Non-Goals:**
- AST-level component analysis (props, variants, slot structure)
- Supporting arbitrary Tailwind projects without shadcn/ui
- Visual rendering or screenshot generation
- Replacing the Figma MCP path (it remains primary when available)

## Decisions

### D1: New `shadcn_parser.py` in `lib/design/`
**Choice:** Separate parser file alongside `fetcher.py` and `design_parser.py`.
**Why:** The shadcn parser is synchronous filesystem I/O (no async MCP), so it doesn't share code with the async Figma fetcher. Separate file keeps each parser focused.
**Alternative considered:** Adding to `design_parser.py` as another `DesignParser` subclass. Rejected because the base class assumes `.make` file input — shadcn reads multiple files from the project root.

### D2: Tailwind config extraction via regex, not AST
**Choice:** Use regex patterns to extract `theme.extend` values from the config file, and parse `@theme` blocks from CSS.
**Why:** Tailwind configs are TypeScript — full AST parsing would require `ts-morph` or subprocess to `node`. Regex covers the common patterns (object literals in `theme.extend`, CSS custom properties) reliably. The config file format is stable and well-structured.
**Alternative considered:** Shell out to `node -e "..."` to evaluate the config. Rejected because it requires Node.js runtime and `tailwindcss` installed, adding brittle dependency.

### D3: Detection in bridge.sh + Python caller in planner.py
**Choice:** `detect_shadcn_project()` in bridge.sh (bash), shadcn parser invoked from Python planner.
**Why:** Consistent with existing pattern — bridge.sh handles detection, planner.py orchestrates fetching. The planner already has the `_fetch_design_context()` method with caching logic.
**Alternative considered:** Pure Python detection. Rejected because bridge.sh is the canonical detection layer (dispatcher and verifier also source it).

### D4: MCP takes priority over local parse
**Choice:** If a design MCP (Figma/Penpot) is registered, always use it. Local shadcn parse is the fallback.
**Why:** MCP provides richer data (screenshots, full component hierarchy from design tool). The shadcn parser is for projects that don't have a design tool at all.

### D5: Snapshot metadata distinguishes source
**Choice:** Add `Source: shadcn-ui` and `Type: local` to the snapshot header metadata.
**Why:** Allows debugging and logging to know where tokens came from. Does not affect downstream parsing (bridge.sh only checks for section headers, not metadata).

## Risks / Trade-offs

**[Risk] Tailwind config format varies** → Regex covers `theme.extend.colors`, `theme.extend.fontFamily`, etc. Edge cases (plugin-generated themes, `presets`) may be missed. Mitigation: document supported patterns, degrade gracefully to CSS-vars-only.

**[Risk] Tailwind v4 adoption is early** → The `@theme` CSS syntax may evolve. Mitigation: parse `@theme` as CSS custom properties (stable format); re-check when Tailwind v4 stabilizes.

**[Risk] Component catalog is filename-only** → No prop/variant extraction. Mitigation: this is sufficient for the dispatch context use case (knowing which components exist, not their full API).

## Open Questions

- Should the parser also extract the `cn()` utility function signature for agent context? (Probably not — agents know shadcn patterns already.)
- Should we support `components.json` v2 format if shadcn introduces breaking changes? (Wait and see — current format has been stable.)
