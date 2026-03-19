## Context

The design bridge (`lib/design/bridge.sh`) currently provides three levels of design context to agents:

1. **Planner** (`design_prompt_section`): Full `design-snapshot.md` content — tokens + component hierarchy links
2. **Dispatcher** (`design_context_for_dispatch`): Filtered Design Tokens + frame-matched Component Hierarchy (max 150 lines)
3. **Verifier** (`build_design_review_section`): Token summary for compliance checking

The problem: Component Hierarchy is a list of **links** to source files, not the source files themselves. Agents get told "there's a ProductCard.tsx" but never see its code. They can't know that the Figma design uses `ShoppingBag` icon for cart, `w-12 h-12` thumbnails in admin tables, or that `shortDescription` appears on product cards.

Meanwhile, `docs/figma-raw/<key>/sources/` contains the actual component code extracted by `wt-figma-fetch`. These files are sitting in the project but never injected into agent context.

## Goals / Non-Goals

**Goals:**
- Agents receive relevant Figma source file contents during dispatch — they see actual component structure, icons, layout patterns
- Planner extracts data model fields from Figma sources (e.g., mockData.ts interface definitions) and embeds them in scope descriptions
- Design review checks component structure (missing icons, missing images, layout divergence), not just token colors
- set-project-web rules guide agents to read Figma source files when present

**Non-Goals:**
- Changing the Figma fetch pipeline itself (wt-figma-fetch works fine)
- Automated visual regression testing (pixel comparison)
- Making design compliance a blocking gate (stays WARNING)
- Framework-specific rules (no React-only logic in bridge.sh)

## Decisions

### D1: Source file matching by keyword extraction from scope text

**Decision**: Reuse the same keyword-matching approach as frame matching — extract meaningful words from scope text, match against source file names (which are path-encoded, e.g., `src__components__ProductCard.tsx`).

**Alternative considered**: Explicit file mapping in planner scope — rejected because it requires the planner to know file names in advance, adding coupling.

**Implementation**: New function `design_sources_for_dispatch()` in `bridge.sh`:
1. Find `docs/figma-raw/*/sources/` directory
2. List all source files
3. Match filenames against scope keywords (case-insensitive, strip `src__` prefix, split on `__`)
4. Return matched file contents with `## Figma Source: <filename>` headers
5. Max budget: 300 lines total (truncate individual files if needed, prefer smaller files)

### D2: Data model extraction for planner

**Decision**: When `sources/` contains a file matching `*mockData*` or `*data*` or `*types*`, extract TypeScript interface definitions and embed entity names + fields in scope instructions to the planner.

**Implementation**: In `design_prompt_section()`, after the snapshot content, append a "## Design Data Model" section with extracted interfaces. This way the planner knows the exact field names (e.g., `shortDescription`, `variants`) and can embed them in scope descriptions.

### D3: Enhanced review section — component structure checks

**Decision**: `build_design_review_section()` extended with a "Component Structure" subsection listing key UI patterns found in source files: icons used, image dimensions, layout containers. The reviewer compares against the diff.

**Implementation**: Parse Figma source files for:
- Icon imports (`import { X } from 'lucide-react'`)
- Image/thumbnail patterns (className containing `w-N h-N` for images)
- Layout patterns (`flex`, `grid`, specific container patterns)
- Build a concise checklist (max 20 items)

### D4: set-project-web rules updates

**Decision**: Update existing rules (not create new ones) — `design-integration.md` and `ui-conventions.md` already exist and are the right place.

Changes:
- `design-integration.md`: Add "Figma Source Files" section — when `docs/figma-raw/*/sources/` exists, agents MUST read matched source files before implementing. Source files are ground-truth for component structure.
- `ui-conventions.md`: Add note that icon choices, image patterns, and layout structures from design source files take priority over generic conventions.

### D5: Context budget management

**Decision**: Source file injection shares a 500-line total budget with existing design context:
- Design Tokens: ~100 lines (unchanged)
- Matched Component Hierarchy: max 100 lines (reduced from 150)
- Matched Source Files: max 300 lines
- Total: ~500 lines max

Files are prioritized by relevance score (keyword match count), then by size (smaller files included first). This prevents context bloat while maximizing useful information.

The 100-line hierarchy cap is enforced unconditionally by passing `max_lines=100` to `design_context_for_dispatch()` (replacing the current 150). The `design_sources_for_dispatch()` function self-enforces its own 300-line cap.

### D6: UI primitive exclusion

**Decision**: Files under `*/ui/*` paths (e.g., `src__components__ui__button.tsx`) are excluded from source file matching. These are shadcn/ui primitives that carry no project-specific design information. In a typical Figma Make project, 50+ of the source files are shadcn primitives — including them would waste most of the 300-line budget on generic component code.

**Implementation**: After filename decoding, check if the decoded path contains `/ui/`. If so, skip the file entirely.

## Risks / Trade-offs

**[Risk: Source files may be stale]** → The bridge already uses cached snapshots. Source files come from the same `wt-figma-fetch` run. If the design changes, user re-runs `wt-figma-fetch --force`. No new staleness risk.

**[Risk: Context size increases agent token usage]** → Mitigated by 500-line total budget. Average Figma source file is 50-100 lines. Typically 3-5 files match, well within budget. Worst case: only most relevant files are included.

**[Risk: Keyword matching may miss relevant files or include irrelevant ones]** → Same approach as frame matching, which works acceptably. False negatives are the common case (some files missed), not false positives. The fallback instruction "read design-snapshot.md for full hierarchy" remains.

**[Risk: Subprocess timeout for source file reading]** → The dispatcher currently uses 5-second timeout for `design_context_for_dispatch`. The new `design_sources_for_dispatch` reads multiple files with bash string processing. Use 10-second timeout for the source function call, consistent with hook timeouts elsewhere.

**[Trade-off: Source files are framework-specific (React/TSX)]** → The bridge doesn't interpret the code, just injects it. Agent models understand TSX well. If a future project uses Vue/Svelte, the same approach works — source files are just text context.
