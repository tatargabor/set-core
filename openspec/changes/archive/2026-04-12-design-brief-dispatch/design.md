# Design: design-brief-dispatch

## Context

The orchestration pipeline has a design integration layer (`lib/design/bridge.sh`, `lib/set_orch/design_parser.py`) that extracts design tokens from Figma sources and injects them into agent contexts. The current dispatch injects inline into `input.md` with a 200-line limit. This works for tokens (~45 lines) but fails for visual descriptions because: (a) design-system.md Page Layouts are skeletal bullet lists, and (b) figma.md rich descriptions are never read by the pipeline.

The existing `set-design-sync` CLI with `design_parser.py` (632 lines) already has `MakeParser`, `PassthroughParser`, and a `DesignSystem` data model with `PageSpec`, `PageSection`, `ComponentSpec`. This infrastructure is extensible.

The architecture requires Layer 1/2 separation: core dispatcher provides the mechanism, project-type profiles can customize matching.

## Goals / Non-Goals

**Goals:**
- Rich visual design descriptions reach implementing agents per-change
- No truncation — full design content available, agent decides what to use
- Backwards compatible — projects without design-brief.md work exactly as before
- Extensible — new design source bridges (Lovable, shadcn) produce the same output format

**Non-Goals:**
- Modifying verify/review gate design compliance (stays [WARNING] level)
- Implementing Lovable or shadcn bridges (separate changes)
- Changing planner-level design token embedding behavior
- Real-time design MCP integration (this is about committed artifacts)

## Decisions

### D1: Per-change design.md file instead of inline injection

**Choice:** Dispatcher writes `openspec/changes/<name>/design.md` with matched content. Input.md includes tokens inline + references the file.

**Why over inline (200-line budget):** Simulation showed 1-5 matched pages per change = 115-266 lines. With tokens+components overhead, some changes exceed 200 lines. Separate file has no limit, agent reads when needed.

**Why over lazy-load-only (just file reference):** Tokens must be inline — they're needed immediately for CSS variable setup. Visual descriptions can be a file reference.

### D2: FigmaMakePromptParser as new parser class in design_parser.py

**Choice:** Add `FigmaMakePromptParser(DesignParser)` that parses the `## N. TITLE` + code block structure of figma.md files.

**Why not modify MakeParser:** MakeParser handles binary .make ZIP files. The figma.md format is a completely different structure (markdown with numbered sections containing Figma Make prompts). Separate parser keeps each format clean.

**Why in design_parser.py (not a new file):** All parsers share the `DesignSystem` data model and `DesignParser` ABC. Keeping them together follows the existing pattern and avoids import complexity.

### D3: to_brief_markdown() as new output method on DesignSystem

**Choice:** Add `to_brief_markdown()` alongside existing `to_markdown()`. The existing method generates design-system.md (lean tokens + component index). The new method generates design-brief.md (rich per-page visual descriptions).

**Why two methods (not one combined file):** Separation of concerns — tokens are always needed (small, inline-safe), visual descriptions are scope-matched (larger, per-change). The dispatcher reads them at different points for different purposes.

### D4: Scope matching via page-name phrases, not single words

**Choice:** Match `## Page: <name>` headers against scope using page name itself + phrase-level aliases. Not single-word keyword matching.

**Why:** Simulation showed single-word matching ("product", "admin", "order") caused 7-13 false-positive page matches per change. Page-name matching ("productcatalog", "admindashboard") + phrase aliases ("hero banner", "product detail") gives 1-5 precise matches.

**Implementation:** Page aliases defined as a dict in bridge.sh or Python. Profile (Layer 2) can override via `design_page_aliases()` method on ProjectType ABC for domain-specific terms.

### D5: Bridge.sh handles file I/O, dispatcher.py orchestrates

**Choice:** `bridge.sh` gets a new function `design_brief_for_dispatch()` that reads design-brief.md + matches pages. `dispatcher.py` calls it and writes the per-change file.

**Why bridge.sh for reading:** Consistent with existing pattern — all design file I/O goes through bridge.sh. The awk/grep matching is already proven in `_dispatch_from_design_system()`.

**Why dispatcher.py for writing:** The per-change directory path and input.md construction are Python-side concerns. Bridge.sh returns matched content to stdout, dispatcher writes it to the right place.

## Risks / Trade-offs

- **[Risk] Page name mismatch between design-brief.md and design-system.md** → Mitigation: `set-design-sync` generates both files from the same source, ensuring consistent page names. Document the canonical page name list.
- **[Risk] Profile alias customization adds complexity** → Mitigation: Default matching works for standard English page names. Profile override is optional, only needed for localized route names.
- **[Risk] Agent ignores design.md file** → Mitigation: design-bridge.md rule already mandates reading design files. Tokens inline in input.md serve as a reminder that design context exists.

## Open Questions

- Should design-brief.md page names be case-sensitive or case-insensitive in matching? (Proposal: case-insensitive)
- Should the `## Components` section from design-system.md go in the per-change design.md or stay inline? (Proposal: include in per-change file — it's always relevant and small)
