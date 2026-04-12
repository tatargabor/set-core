## Why

The review learnings pipeline has structural gaps that prevent it from fulfilling its core promise: ensuring agents don't repeat mistakes across changes and runs. The review gate never sees the learnings checklist (only the agent's input.md gets it), deduplication uses naive 60-char prefix matching causing semantic duplicates to fill the 50-entry cap, the classifier marks everything as "template" scope, and there's no relevance-based filtering — agents receive the full checklist regardless of whether the learnings are relevant to their change scope.

## What Changes

- **Review gate learnings injection**: Pass the persistent learnings checklist into the review prompt template so the reviewer LLM can actually enforce violations (currently the "review will BLOCK if violated" header is an empty promise)
- **LLM-based semantic deduplication**: Replace 60-char prefix normalization with LLM merge pass that consolidates semantically identical patterns (e.g., "No middleware.ts" / "Missing src/middleware.ts" / "No middleware — admin routes unprotected" → single entry)
- **Scope-aware learnings filtering**: At dispatch time, use diff content classification (auth/api/database/frontend categories from `classify_diff_content()`) to select only relevant learnings for the agent's change scope, rather than dumping the full checklist
- **Remove hard cap / add relevance-weighted eviction**: Replace fixed cap=50 with count*severity-weighted LRU eviction and raise ceiling to 200 entries, ensuring high-signal patterns survive
- **Classifier prompt improvement**: Add few-shot examples to the template/project classifier so domain-specific patterns stop being misclassified as "template"
- **Expand review pattern clusters**: Add IDOR, cascade-delete, race-condition, missing-validation, open-redirect clusters to improve cross-change learning signal
- **Truncate fix_hint storage**: Cap fix_hint at 200 chars to prevent bloated JSONL entries

## Capabilities

### New Capabilities
- `learnings-dedup` — LLM-based semantic deduplication of review learnings entries
- `learnings-scope-filter` — Scope-aware filtering of learnings at dispatch time based on diff content categories

### Modified Capabilities
- `review-learnings` — Review gate injection, eviction policy, classifier improvement, cluster expansion, fix_hint truncation

## Impact

**Core (lib/set_orch/)**:
- `templates.py` — `render_review_prompt()` gains `learnings_checklist` parameter
- `verifier.py` — `review_change()` and `_execute_review_gate()` pass learnings through
- `profile_types.py` — `_merge_learnings()` eviction logic, `_classify_patterns()` prompt, `review_learnings_checklist()` scope filtering
- `dispatcher.py` — `_build_review_learnings()` uses content categories for filtering
- `review_clusters.py` — expanded cluster definitions
- `cli.py` — template CLI passes learnings field

**Web Module (modules/web/)**:
- No changes expected (baseline stays in review_baseline.md)

**No breaking changes** — all modifications are additive to existing interfaces.
