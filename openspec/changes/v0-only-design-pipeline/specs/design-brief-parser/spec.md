# Spec: Design Brief Parser (delta)

## REMOVED Requirements

### Requirement: Parse Figma Make prompt files

**Reason:** Figma Make prompt files (`figma.md`) are no longer an input format. The framework consumes v0 ZIP exports directly, not human-authored Figma prompts.

**Migration:** Scaffold authors who previously wrote `figma.md` SHOULD now write `docs/v0-prompts.md` (one v0.dev prompt per page) and use them in v0.app to generate the design. The resulting export is consumed via `set-design-import`. The v0-prompts.md is committed alongside v0-export/ as audit trail but is NOT parsed by the framework.

### Requirement: Generate design-brief.md output

**Reason:** `design-brief.md` is no longer the authoritative design spec for orchestration. Optional vibe notes MAY remain in `docs/design-brief.md` but are non-authoritative (the design-bridge spec covers this). Auto-generation of brief content from prompts is removed.

**Migration:** If a scaffold needs vibe notes (brand personality, references, AVOID list), the author writes `docs/design-brief.md` directly as a short non-authoritative document. The framework does NOT parse it.

### Requirement: Parser data model

**Reason:** `PageSpec`, `DesignSystem`, and related dataclasses tied to figma.md parsing are removed along with the parser code. Token/component/page extraction is no longer performed because the v0 TSX files are the source.

**Migration:** Internal callers within the removed pipeline (set-design-sync, design-brief-stem-match) are also removed. No external API depended on these dataclasses.
