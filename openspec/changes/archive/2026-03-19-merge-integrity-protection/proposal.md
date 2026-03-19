# Proposal: Merge Integrity Protection

## Why

When parallel changes modify shared files (DB schemas, middleware, config registries), the LLM-based merge resolver can silently lose content — model definitions, route entries, export statements. The current pipeline has no post-merge validation, so data loss propagates: agents work around missing definitions with type hacks (`any`), builds pass, mocked tests pass, and the error surfaces only at runtime. In practice, LLM resolvers can silently lose content — database models, route entries, export statements — without any post-merge validation to catch the loss.

The core principle: **FAIL LOUD > SILENT CORRUPTION**. If a merge cannot verify correctness, it must block — not guess.

## What Changes

- **New**: Post-LLM merge conservation check in `wt-merge` — after LLM resolves conflicts, verify that additions from both sides are preserved before committing
- **New**: File-type-aware merge strategies — configurable per-file rules (additive-only for schemas) with LLM hints and post-merge validation commands
- **New**: `--no-conservation-check` flag on `wt-merge` for emergency bypass when conservation check produces false positives
- **New**: `merge_strategies` configuration in `project-knowledge.yaml` — projects declare file patterns, strategy types, entity patterns, validation commands, and LLM context hints
- **New**: Entity conservation counting — count named entities (models, exports, classes, routes) before/after LLM merge, block if count drops
- **Modified**: `llm_resolve_conflicts()` in `wt-merge` — receives file-type context and LLM hints from merge strategy config, sends enriched prompts
- **Modified**: Profile system — profiles can supply default merge strategies (e.g., `set-project-web` ships Prisma/middleware/i18n strategies)
- **New**: Agent rule prohibiting `any` type on database client parameters — deployed to consumer projects via `set-project init`

## Capabilities

### New Capabilities
- `merge-conservation-check` — Generic diff-based verification that LLM merges preserve additions from both sides
- `merge-file-type-strategy` — Configurable per-file merge strategies with entity counting, validation commands, and LLM prompt enrichment

### Modified Capabilities
- (none — existing merge pipeline spec covers the bash-level wt-merge, these are new verification layers)

## Impact

- **wt-merge**: `bin/wt-merge` — new conservation check after LLM resolve, file-type strategy lookup, enriched LLM prompts
- **Profile system**: `lib/set_orch/profile_loader.py` — profiles supply default `merge_strategies`
- **Config**: `project-knowledge.yaml` gains `merge_strategies` section
- **Agent rules**: new `.claude/rules/web/db-type-safety.md` — prohibits `any` on DB parameters
- **Templates**: `templates/project-knowledge.yaml` updated with merge strategy examples
- **set-project-web**: ships Prisma, middleware, i18n default strategies (separate package update)
