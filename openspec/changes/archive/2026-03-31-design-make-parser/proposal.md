# Proposal: design-make-parser

## Why

The design pipeline is broken: agents receive Tailwind class statistics instead of actual brand tokens, resulting in apps that look like generic shadcn templates instead of the Figma design. The root cause is that the design-snapshot.md generated from Figma Make exports contains only class frequency counts (e.g., `bg-white (×74)`) rather than actual hex colors, font families, and component layouts.

Meanwhile, the Figma Make `.make` export file contains everything needed: a structured `ai_chat.json` with all generated React components (`theme.css` with CSS custom properties, `Header.tsx`, `Footer.tsx`, page layouts, Unsplash image queries). This data is perfectly parseable but currently unused by the pipeline.

Additionally, there is no documentation guiding users on spec quality and design integration before starting a sentinel run — users jump straight to `sentinel start` without ensuring their specs reference concrete design values.

## What Changes

### New CLI Tool: `set-design-sync`

A pre-pipeline tool that users run before sentinel/orchestration to extract design tokens from a Figma Make `.make` export and inject them into spec files.

**Usage:**
```bash
set-design-sync --input docs/design.make --spec-dir docs/
```

**Input formats (extensible):**
- `.make` file (Figma Make export — primary, implemented now)
- `design-system.md` file (manual — passthrough, no parsing needed)
- Future: `.fig` via Figma API, Penpot export, Stitch, etc.

**Outputs:**
1. `docs/design-system.md` — Structured design tokens + page layouts extracted from the `.make` file
2. Updated spec files in `--spec-dir` — Adds `## Design Reference` sections with page-specific token references
3. Updated `set/orchestration/config.yaml` — Sets `design_file` pointer

**Spec update logic:**
- Scans spec `.md` files for page/feature keywords (homepage, catalog, cart, checkout, admin, etc.)
- Matches against design-system.md page sections
- Adds/replaces `## Design Reference` section with: page name, key layout elements, critical tokens
- Does NOT modify other spec content — only appends/replaces the Design Reference section

### Dispatcher Integration Update

- `design_context_for_dispatch()` updated: reads from `docs/design-system.md` first (structured tokens), falls back to `design-snapshot.md`
- Page-specific injection: scope text matched against design-system.md sections → agent gets only the relevant page's design spec

### Documentation

- New guide: `docs/guide/design-integration.md` — How to prepare specs with design context before running sentinel
- Updated: `docs/guide/orchestration.md` — Add "Pre-Run Checklist" section referencing design sync
- Updated: `docs/guide/sentinel.md` — Add "Spec Quality" prerequisites section

## Capabilities

### New Capabilities
- `design-make-parser`: Parse Figma Make `.make` exports into structured design-system.md
- `design-spec-sync`: Inject design references into spec files
- `design-integration-guide`: Documentation for design-to-code workflow

### Modified Capabilities
- `design-dispatch-context`: Use design-system.md as primary source for dispatch context

## Impact

- **New files**: `bin/set-design-sync` (CLI), `lib/set_orch/design_parser.py` (parser), `docs/guide/design-integration.md`
- **Modified files**: `lib/design/bridge.sh` (dispatch fallback), `docs/guide/orchestration.md`, `docs/guide/sentinel.md`
- **Dependencies**: None (standard library only — zipfile, json, re)
- **Risk**: Low — new tool, doesn't change existing pipeline behavior unless design-system.md exists
