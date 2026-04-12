## Context

The review learnings pipeline was built in three phases: cross-change injection (within-run), persistent storage (cross-run), and dispatch-time checklist. It works end-to-end — learnings are captured, stored, and injected into agent input.md. However, production runs (minishop, craftbrew) revealed structural weaknesses:

1. The review gate LLM never sees learnings — only the implementation agent does
2. Deduplication uses 60-char prefix matching, causing near-duplicates ("No middleware.ts" vs "Missing src/middleware.ts") to waste slots
3. The cap of 50 is reached, and old-but-important patterns get evicted by newer low-signal ones
4. All patterns are classified as "template" scope regardless of actual specificity
5. Agents receive the full unfiltered checklist even when most items are irrelevant to their change scope

The existing `classify_diff_content()` system in `templates.py` provides a proven pattern: classify diff content into categories (auth, api, database, frontend) and inject targeted review instructions. We extend this to learnings.

## Goals / Non-Goals

**Goals:**
- Review gate enforces learnings (not just the agent)
- Semantically identical learnings merge into single entries
- Agents receive only scope-relevant learnings
- High-signal patterns survive longer than low-signal ones
- Classifier correctly distinguishes template vs project patterns

**Non-Goals:**
- Changing when learnings are captured (post-review timing stays)
- Modifying the baseline system (review_baseline.md is fine)
- Building a learnings UI/dashboard
- Cross-project learnings sharing beyond template JSONL

## Decisions

### D1: Review gate injection via prompt_prefix (not template change)

The review gate already has a `prompt_prefix` mechanism used by shadcn enforcement and e2e coverage gaps (`verifier.py:2549-2564`). Learnings injection follows this same pattern — build a learnings prefix in `_execute_review_gate()` and prepend it, rather than modifying `render_review_prompt()` signature.

**Rationale:** The prompt_prefix path is simpler, doesn't require CLI/template changes, and keeps the review template focused on the diff review task. The learnings act as pre-review context, same as shadcn enforcement does.

**Alternative considered:** Adding `learnings_checklist` param to `render_review_prompt()` → rejected because it changes the template API, requires CLI plumbing, and the prefix pattern is already proven.

### D2: LLM dedup at merge time, not at query time

Semantic deduplication runs during `persist_review_learnings()` (merge-time), not during `review_learnings_checklist()` (query-time). A Sonnet call checks if new patterns are semantically equivalent to existing entries and merges them.

**Rationale:** Merge-time is infrequent (once per change merge), query-time is frequent (every dispatch). LLM calls at merge-time have negligible cost. Running dedup at merge also means the JSONL is always clean — every reader benefits.

**Algorithm:**
1. After classification, before writing: batch all new+existing patterns into a Sonnet call
2. Prompt: "Group semantically identical patterns. Return merge groups as `[[idx1, idx2], [idx3]]`"
3. For each group: keep highest-count entry, sum counts, union source_changes, keep most recent last_seen
4. Fallback on LLM error: skip dedup (safe — no data loss)

### D3: Scope-aware filtering uses diff content categories

At dispatch time, `_build_review_learnings()` and `review_learnings_checklist()` accept a `content_categories: set[str]` parameter (from `classify_diff_content()`). Each learning entry gets a category tag (auth, api, database, frontend, general). Only entries matching the change's categories (plus "general") are injected.

**Category tagging:** Done during persist, not query. Each pattern gets a `categories: list[str]` field based on keyword matching (same keywords as `classify_diff_content` uses). Patterns that don't match any category get `["general"]`.

**Alternative considered:** LLM-based relevance scoring at dispatch time → rejected because it adds latency to every dispatch and the keyword approach is sufficient given learnings are already human-readable descriptions.

### D4: Severity-weighted eviction replaces timestamp-only LRU

New eviction formula: `score = count * severity_weight * recency_factor`
- `severity_weight`: CRITICAL=3, HIGH=2, MEDIUM=1
- `recency_factor`: `1.0` if seen in last 7 days, `0.7` if 7-30 days, `0.4` if >30 days
- Cap raised to 200 entries
- Eviction triggers at 200, removes lowest-score entries down to 180 (hysteresis to avoid evict-every-merge)

**Rationale:** A pattern seen 8x across runs with CRITICAL severity should never be evicted by a 1x MEDIUM pattern just because it's newer.

### D5: Classifier prompt with few-shot examples

The classifier prompt currently has zero examples. We add 4 example patterns with expected classifications:

- "No authentication middleware on API routes" → template
- "Budapest postal code validation missing" → project
- "IDOR — any user can modify other users' resources" → template
- "Product name must be unique per brewery" → project

**Rationale:** Few-shot examples are the simplest intervention with the highest ROI for classification accuracy.

### D6: Cluster expansion is static (no LLM)

New clusters added to `review_clusters.py`:
- `"idor"`: ["idor", "ownership", "authorization check", "other users"]
- `"cascade-delete"`: ["cascade", "financial data", "order history"]
- `"race-condition"`: ["race condition", "atomic", "double-spend", "oversell"]
- `"missing-validation"`: ["input validation", "accepts negative", "zod validation"]
- `"open-redirect"`: ["open redirect", "redirect vulnerability"]

**Rationale:** These patterns appear frequently in the current web.jsonl (50 entries). Static keyword matching is cheap and deterministic.

## Risks / Trade-offs

**[Risk] LLM dedup merges dissimilar patterns** → Mitigation: Conservative prompt ("only merge if they describe the EXACT same issue"), fallback to no-merge on error. Can be disabled via directive `learnings_llm_dedup_enabled: false`.

**[Risk] Scope filtering drops relevant learnings** → Mitigation: "general" category is always included. If a pattern doesn't match any specific category, it goes to "general". Agent still sees all cross-category patterns like "missing trailing newline".

**[Risk] 200-entry cap increases checklist size** → Mitigation: Scope filtering means agents see ~20-40 relevant items, not all 200. The checklist injected into input.md and review prompt is already filtered.

**[Trade-off] Extra Sonnet call per merge for dedup** → Acceptable: merges are infrequent (~6 per run, ~1 per hour), and Sonnet calls are cheap (~$0.01 each).

## Open Questions

None — all decisions are based on observed production behavior.
