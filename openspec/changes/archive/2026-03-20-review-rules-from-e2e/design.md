# Design: review-rules-from-e2e

## Context

E2E review analysis of a consumer project orchestration run identified 89 issues (19 CRITICAL, 33 HIGH) across 3 changes. Analysis showed 60% were already covered by existing rules (agent compliance issue, not a rules gap), but 40% represent genuinely new patterns not covered by any rule in `.claude/rules/web/`. This change adds those missing patterns.

The existing rule files in `.claude/rules/web/` follow a consistent format: problem description, wrong pattern (with code), correct pattern (with code), and a bold "The rule:" summary statement. New content must match this format exactly.

## Goals / Non-Goals

**Goals:**
- Add 3 new sections to `transaction-patterns.md` (sections #5, #6, and expand #3)
- Add 1 new section to `security-patterns.md` (section #9)
- Add 1 new section to `api-design.md` (section #6)
- Create `schema-integrity.md` with 4 sections
- Create `nextjs-patterns.md` with 2 sections

**Non-Goals:**
- Modifying agent behavior to improve compliance with existing rules (separate concern)
- Adding enforcement tooling (linting, static analysis) — rules are documentation-level
- Changing rule file loading or resolution logic in set-core

## Decisions

### 1. Extend existing files vs create new files

**Decision:** Extend `transaction-patterns.md`, `security-patterns.md`, and `api-design.md` with new numbered sections. Create new files for `schema-integrity.md` and `nextjs-patterns.md`.

**Rationale:** Transaction safety extensions (payment rollback, soft status, atomic finite resources) are natural extensions of the existing transaction patterns. Secret code enumeration is a security pattern. Validation deduplication is an API design pattern. Schema integrity and Next.js patterns are distinct domains warranting their own files.

**Alternative considered:** Putting everything in one large "e2e-findings.md" file. Rejected because rules should be organized by domain, not by discovery source.

### 2. Rename section #3 from "Atomic Inventory Operations" to "Atomic Finite Resource Operations"

**Decision:** Rename the heading and expand the content to cover gift cards, coupons, and seat counts alongside inventory.

**Rationale:** The atomic conditional update pattern is identical for all finite resources. Keeping them separate would duplicate the same WHERE-conditional-update pattern multiple times.

**Alternative considered:** Adding separate sections for each resource type. Rejected as redundant — the pattern is identical, only the resource name changes.

### 3. YAML frontmatter for new files

**Decision:** New files (`schema-integrity.md`, `nextjs-patterns.md`) must include the same YAML frontmatter format as existing rule files, with `description` and `globs` fields.

**Rationale:** The frontmatter controls when rules are surfaced to agents. Without correct globs, rules won't appear in context for relevant file edits.

## Risks / Trade-offs

- **[Risk] Expanding #3 heading is a breaking reference** — Other docs or memory entries may reference "Atomic Inventory Operations" by name. Mitigation: The old name appears only in rule files that we control. A search-and-replace during implementation will catch any stale references.
- **[Risk] Next.js patterns may become stale** — Next.js APIs evolve rapidly (e.g., `unstable_cache` may be renamed). Mitigation: Keep patterns generic enough to survive minor API renames. Note the framework version context in the file.
- **[Risk] Over-specific code examples** — Rule examples using Prisma syntax may confuse projects using other ORMs. Mitigation: Existing rules already use Prisma examples with a note that patterns apply to all ORMs. Follow the same convention.

## Migration Plan

No migration needed. Rules are static markdown files deployed via `set-project init`. Consumer projects receive updates on next init run.

## Open Questions

None — all patterns are well-understood from the E2E analysis.
