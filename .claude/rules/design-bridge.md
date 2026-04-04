# Design Tool Integration

## Design files in this project

The design pipeline uses up to three design files:

- **`design-system.md`** — Design tokens (colors, fonts, spacing, radii). Always read this for CSS variables.
- **`design-brief.md`** — Per-page visual descriptions (layout, components, responsive behavior). Read the pages relevant to your change.
- **`design.md` (per-change)** — If present in `openspec/changes/<name>/`, this contains scope-matched design tokens + visual descriptions specific to your change. Read this FIRST.

## When a per-change `design.md` exists:

1. You MUST read `design.md` in your change directory BEFORE implementing any UI component
2. Use the EXACT color, spacing, typography, and radius values from the Design Tokens section — do NOT fall back to shadcn/ui defaults if they differ from the design
3. Follow the Visual Design sections for layout structure, component placement, CTA text, and responsive behavior
4. If the design specifies `bg-[#78350F]` for buttons but your framework default is `bg-primary`, use the design value explicitly
5. Report design gaps — if you need a design spec that doesn't exist, note it as a `design_gap` in your output

## When `design-snapshot.md` or `design-system.md` exists (but no per-change design.md):

1. You MUST read the design file BEFORE implementing any UI component
2. Use the EXACT token values from the Design Tokens section
3. Match the component hierarchy structure from the relevant frame
4. If `design-brief.md` also exists, read the pages relevant to your scope for visual details

## Orchestration pipeline integration

The design pipeline is automated — these happen without manual intervention:

- **Pre-orchestration:** `set-design-sync` generates `design-system.md` (tokens) and `design-brief.md` (visual descriptions) from design sources (Figma Make, .make files)
- **Planner:** reads design files as part of spec, embeds token values in change scope descriptions
- **Dispatch:** scope-matches `design-brief.md` pages → writes per-change `design.md` with tokens + matched visual descriptions. Agent's `input.md` references this file.
- **Verify gate:** `build_design_review_section()` adds a design compliance check to the code review prompt — token mismatches are reported as [WARNING], not [CRITICAL]

## When a design MCP server (figma, penpot, sketch, zeplin) is available but no snapshot exists:

1. You MUST query the design tool for specs BEFORE implementing UI elements: colors, spacing, typography, layout, component structure
2. Use design tokens from the tool rather than hardcoding values
3. Match component hierarchy from the design

## When neither design tools nor design files are available:

Ignore this rule entirely.
