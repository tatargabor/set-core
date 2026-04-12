# Proposal: design-brief-dispatch

## Why

Orchestration agents receive design tokens (colors, fonts, spacing) but NOT visual design descriptions. The `design-system.md` Page Layouts section contains only bullet lists ("Hero Banner", "Featured Coffees") without describing what these sections look like. Meanwhile, detailed Figma Make prompt files (`figma.md`) with full visual specifications (layout dimensions, CTA text, component structure, responsive behavior) exist in project scaffolds but are never read by the pipeline. This results in agents producing functionally correct but visually skeletal UIs — correct colors and fonts but empty heroes, unstyled CTAs, missing product grids.

## What Changes

- **New**: `FigmaMakePromptParser` in `design_parser.py` — parses `figma.md` prompt collections into page-structured design briefs
- **New**: `to_brief_markdown()` on `DesignSystem` — generates `design-brief.md` with `## Page: <name>` sections
- **New**: Per-change `design.md` generation at dispatch time — dispatcher writes scope-matched design brief pages to each change's directory
- **MODIFIED**: `design_context_for_dispatch()` in `bridge.sh` — reads `design-brief.md` alongside `design-system.md`, writes per-change file instead of inline injection
- **MODIFIED**: `_build_input_content()` in `dispatcher.py` — references per-change `design.md` file instead of inline Design Context section
- **MODIFIED**: `set-design-sync` CLI — accepts `figma.md` as input format, outputs both `design-system.md` (tokens) and `design-brief.md` (visual descriptions)
- **MODIFIED**: Scaffold `design-system.md` — cleanup: remove skeletal Page Layouts, keep only tokens and component index
- **MODIFIED**: Design-related documentation — update examples referencing the new file structure

## Capabilities

### New Capabilities
- `design-brief-parser` — Parse Figma Make prompt files into structured per-page visual design briefs
- `per-change-design-dispatch` — Generate scope-matched design files per change at dispatch time

### Modified Capabilities
- `design-dispatch-context` — Read design-brief.md for page-specific visual descriptions, write per-change design.md
- `design-snapshot` — set-design-sync accepts figma.md format, outputs design-brief.md alongside design-system.md

## Impact

- `lib/set_orch/design_parser.py` — new parser class + output method
- `lib/design/bridge.sh` — design-brief.md reading + per-change file writing
- `lib/set_orch/dispatcher.py` — reference per-change design.md instead of inline section
- `bin/set-design-sync` — already works, parser auto-detection handles new format
- `tests/e2e/scaffolds/craftbrew/` — design-system.md cleanup, design-brief.md generation
- `tests/e2e/runners/run-craftbrew.sh` — add set-design-sync call
- `.claude/rules/design-bridge.md` — update to reference design-brief.md
- `docs/` — update design pipeline documentation
