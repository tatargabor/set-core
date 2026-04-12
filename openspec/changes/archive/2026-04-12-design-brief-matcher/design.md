# Design: design-brief-matcher

## Context

`design_brief_for_dispatch()` in `lib/design/bridge.sh` matches page names from design-brief.md against change scope text. Currently it only does exact substring matching, which fails when decompose generates scope descriptions that don't contain the literal page name.

The `_dispatch_from_design_system()` function already has bidirectional matching (line 431-435) using `tr ' ' '|'` to convert scope words into an OR regex. However, this single-word approach is too aggressive — "product" in scope matches "Admin Products" page.

## Goals / Non-Goals

**Goals:**
- Page matching works with natural language scope descriptions
- No false positives (storefront pages don't match admin scopes)
- Aliases are scaffold-specific, not hardcoded in core

**Non-Goals:**
- NLP or fuzzy matching — keep it deterministic bash
- Changing the existing exact or alias matching layers
- Modifying `_dispatch_from_design_system()` to match this approach

## Decisions

### Decision 1: ALL-words-must-match stem strategy

**Choice:** For stem bidir matching, ALL words (3+ chars) of the page name must have their stem (first 4 chars) found in the scope text.

**Why not single-word matching?** (like `_dispatch_from_design_system`): Testing shows "product catalog browsing" falsely matches "Admin Products" because "product" alone matches. Requiring ALL words eliminates this — "Admin Products" needs both "admi" and "prod" stems.

**Why 4-char stems?** Handles plurals and verb forms: "products"→"prod" matches "product", "orders"→"orde" matches "order". Shorter stems (3) would over-match: "pro" matches "product", "profile", "prometheus". Longer stems (5) would miss: "produ" doesn't match "product" in "product".

**Alternative considered:** Levenshtein distance — too complex for bash, adds dependency. The 4-char stem is simple and handles the real cases.

### Decision 2: Empty default aliases, scaffold files for overrides

**Choice:** Clear `_DESIGN_BRIEF_ALIASES` array, move entries to `tests/e2e/scaffolds/craftbrew/docs/design-brief-aliases.txt`.

**Why:** The current hardcoded aliases are craftbrew-specific (hungarian terms like "kavek", "penztar", "elofizetes"). Per modular architecture, project-specific content belongs at scaffold level. The `DESIGN_BRIEF_ALIASES_FILE` mechanism already exists.

**Deployment:** Runner scripts copy alias file to project docs/ and add `DESIGN_BRIEF_ALIASES_FILE` to orchestration environment. The engine passes this env var to subprocess calls.

### Decision 3: Auto-discovery of alias file next to brief

**Choice:** `design_brief_for_dispatch()` auto-discovers `docs/design-brief-aliases.txt` (same directory as `design-brief.md`) when `DESIGN_BRIEF_ALIASES_FILE` env var is not set. The runner simply copies the scaffold's alias file to `docs/` alongside the brief.

**Why auto-discovery?** The runner starts the sentinel via HTTP API to the manager process. Env vars don't propagate through HTTP calls. The file-based convention (`docs/design-brief-aliases.txt`) follows the existing pattern where design files live in `docs/`.

**Fallback chain:** `DESIGN_BRIEF_ALIASES_FILE` (env var) → `docs/design-brief-aliases.txt` (convention) → empty (no aliases).

## Risks / Trade-offs

- **[Risk] 4-char stem too short for some languages** → Mitigation: Only affects English page names currently. Can increase to 5 if needed.
- **[Risk] Stem matching changes may affect existing working scaffolds** → Mitigation: Stem is third layer, only fires when exact and alias both miss. Existing exact matches are unaffected.
- **[Risk] Config.yaml alias path needs dispatcher support** → Mitigation: Dispatcher already reads config for other settings. Small addition.

## Open Questions

None — design is straightforward.
