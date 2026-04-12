## 1. Review Gate Learnings Injection

- [x] 1.1 In `verifier.py:_execute_review_gate()`, load the persistent learnings checklist via `profile.review_learnings_checklist()` and build a `learnings_prefix` string formatted as review context [REQ: review-gate-receives-learnings-checklist]
- [x] 1.2 Prepend the `learnings_prefix` to `combined_prefix` (after shadcn + e2e coverage prefixes) so it reaches the review LLM via the existing `prompt_prefix` mechanism [REQ: review-gate-receives-learnings-checklist]
- [x] 1.3 Format the learnings prefix to instruct the reviewer: patterns with count>=3 and CRITICAL severity should be treated as [CRITICAL] findings if violated; others as [HIGH] [REQ: review-gate-receives-learnings-checklist]

## 2. Semantic Deduplication

- [x] 2.1 Add `_dedup_learnings(entries: list[dict]) -> list[dict]` method to `ProfileTypes` in `profile_types.py` that sends all entries to Sonnet with a conservative merge prompt [REQ: semantic-dedup-at-merge-time]
- [x] 2.2 Design the dedup prompt: send pattern texts with indices, ask for JSON merge groups `[[0,2,4],[1],[3]]`, include instruction "only merge if they describe the EXACT same issue" [REQ: dedup-prompt-design]
- [x] 2.3 Implement merge logic: for each group, keep entry with shortest clear `pattern` text, sum `count`, union `source_changes` (cap 10), take most recent `last_seen`, preserve highest `severity` [REQ: semantic-dedup-at-merge-time]
- [x] 2.4 Call `_dedup_learnings()` in `persist_review_learnings()` after classification and before writing to JSONL [REQ: semantic-dedup-at-merge-time]
- [x] 2.5 Add fallback: if Sonnet call fails (exit_code!=0 or unparseable JSON), log WARNING and skip dedup [REQ: llm-dedup-call-fails]

## 3. Category Tagging

- [x] 3.1 Define `LEARNINGS_CATEGORY_KEYWORDS` dict in `profile_types.py` mapping categories to keyword lists (reuse keywords from `templates.py:classify_diff_content` patterns: auth, api, database, frontend) [REQ: category-tagging-at-persist-time]
- [x] 3.2 Add `_assign_categories(pattern: str, fix_hint: str) -> list[str]` function that returns matching categories or `["general"]` if none match [REQ: category-tagging-at-persist-time]
- [x] 3.3 Call `_assign_categories()` during `persist_review_learnings()` to populate `categories` field on each entry [REQ: category-tagging-at-persist-time]
- [x] 3.4 In `_merge_learnings()`, backfill `categories` for existing entries that lack the field [REQ: existing-entries-without-categories-get-backfilled]

## 4. Scope-Aware Filtering

- [x] 4.1 Add optional `content_categories: set[str] | None = None` parameter to `review_learnings_checklist()` in `profile_types.py` [REQ: scope-filtered-checklist-at-dispatch]
- [x] 4.2 When `content_categories` is provided, filter entries to those whose `categories` overlap with `content_categories | {"general"}` [REQ: scope-filtered-checklist-at-dispatch]
- [x] 4.3 In `dispatcher.py:dispatch_change()`, call `classify_diff_content()` on the change scope and pass the categories to `review_learnings_checklist()` [REQ: dispatcher-passes-content-categories]
- [x] 4.4 Pass the same categories to `_build_review_learnings()` for within-run filtering consistency [REQ: dispatcher-passes-content-categories]

## 5. Eviction Policy

- [x] 5.1 Add `_eviction_score(entry: dict) -> float` function implementing `count * severity_weight * recency_factor` formula in `profile_types.py` [REQ: severity-weighted-eviction-replaces-timestamp-lru]
- [x] 5.2 Update `_merge_learnings()`: change `cap` default from 50 to 200, add hysteresis (evict to 180 when 200 reached) [REQ: severity-weighted-eviction-replaces-timestamp-lru]
- [x] 5.3 Replace `entries.sort(key=lambda e: e.get("last_seen", ""))` with `entries.sort(key=_eviction_score)` for eviction ordering [REQ: severity-weighted-eviction-replaces-timestamp-lru]

## 6. Classifier Improvement

- [x] 6.1 Add 4+ few-shot examples to `_classify_patterns()` prompt in `profile_types.py`: 2 template examples (auth middleware, IDOR) and 2 project examples (domain validation, business rule) [REQ: classifier-prompt-includes-few-shot-examples]

## 7. Cluster Expansion

- [x] 7.1 Add new clusters to `REVIEW_PATTERN_CLUSTERS` in `review_clusters.py`: `idor`, `cascade-delete`, `race-condition`, `missing-validation`, `open-redirect` with appropriate keyword lists [REQ: expanded-review-pattern-clusters]
- [x] 7.2 Add corresponding labels to `_CLUSTER_LABELS` in `dispatcher.py:_build_review_learnings()` [REQ: expanded-review-pattern-clusters]

## 8. fix_hint Truncation

- [x] 8.1 In `persist_review_learnings()`, truncate `fix_hint` to 200 chars before writing to JSONL — strip code blocks first, then truncate with trailing `...` [REQ: fix_hint-truncated-at-storage]

## 9. Existing JSONL Cleanup

- [x] 9.1 Write a one-time migration in `persist_review_learnings()` or a standalone script that re-processes `~/.config/set-core/review-learnings/web.jsonl`: run dedup, assign categories, truncate fix_hints, apply new eviction [REQ: semantic-dedup-at-merge-time]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN review gate runs THEN review prompt includes learnings via prompt_prefix with severity and count [REQ: review-gate-receives-learnings-checklist, scenario: review-prompt-includes-learnings]
- [x] AC-2: WHEN no learnings exist THEN review prompt has no learnings prefix [REQ: review-gate-receives-learnings-checklist, scenario: no-learnings-available]
- [x] AC-3: WHEN near-duplicate patterns exist THEN they are merged into single entry with aggregated count and source_changes [REQ: semantic-dedup-at-merge-time, scenario: near-duplicate-patterns-merged]
- [x] AC-4: WHEN LLM dedup fails THEN entries are written as-is with WARNING log [REQ: semantic-dedup-at-merge-time, scenario: llm-dedup-call-fails]
- [x] AC-5: WHEN auth change dispatched THEN checklist contains only auth+general learnings [REQ: scope-filtered-checklist-at-dispatch, scenario: auth-change-gets-auth-general-learnings]
- [x] AC-6: WHEN no content_categories provided THEN all entries returned (backward compat) [REQ: scope-filtered-checklist-at-dispatch, scenario: no-content-categories-provided]
- [x] AC-7: WHEN JSONL reaches 200 entries THEN lowest-score entries evicted to 180 [REQ: severity-weighted-eviction-replaces-timestamp-lru, scenario: eviction-hysteresis]
- [x] AC-8: WHEN high-count CRITICAL pattern competes with low-count recent pattern THEN high-count survives [REQ: severity-weighted-eviction-replaces-timestamp-lru, scenario: high-signal-pattern-survives]
- [x] AC-9: WHEN classifier runs THEN prompt includes few-shot template/project examples [REQ: classifier-prompt-includes-few-shot-examples, scenario: classifier-uses-examples]
- [x] AC-10: WHEN IDOR patterns found in findings THEN they cluster under "idor" in cross-change learnings [REQ: expanded-review-pattern-clusters, scenario: idor-patterns-clustered]
- [x] AC-11: WHEN fix_hint exceeds 200 chars THEN it is truncated with trailing `...` [REQ: fix_hint-truncated-at-storage, scenario: long-fix_hint-truncated]
