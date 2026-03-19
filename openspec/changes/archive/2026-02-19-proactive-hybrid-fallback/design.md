## Context

`set-memory proactive` is used by all 5 hook layers (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, SubagentStop) to surface relevant memories. It calls shodh-memory's `proactive_context()` which uses pure semantic similarity. This works well for English technical queries but fails for:
- Short queries ("levelibéka") — too little semantic content
- Non-English text ("mac és alwaysontop") — embedding model is English-centric
- Abbreviated terms — embedding distance is too large

Meanwhile, `set-memory recall --mode hybrid` (semantic + keyword) finds these memories reliably. The two functions use the same underlying database but different retrieval strategies.

Current `cmd_proactive` code (lines ~706-729 of `bin/set-memory`):
```python
if hasattr(m, 'proactive_context'):
    raw = m.proactive_context(context, max_results=limit, auto_ingest=False, semantic_threshold=0.3)
    results = raw.get('memories', []) if isinstance(raw, dict) else raw
else:
    results = m.recall(context, limit=limit, mode='hybrid')
```

The `else` branch (hybrid fallback) only runs if `proactive_context` doesn't exist — it never runs as a quality fallback.

## Goals / Non-Goals

**Goals:**
- Improve proactive recall quality for short, non-English, and abbreviated queries
- Use hybrid recall as fallback when proactive returns insufficient results
- Maintain consistent JSON output format (relevance_score on all results)
- Zero impact on hook code — fix entirely in `cmd_proactive`

**Non-Goals:**
- Changing the shodh-memory library itself
- Modifying the hook layer's filtering logic
- Replacing proactive_context entirely (it's still better for long, English queries)

## Decisions

### Decision 1: Fallback trigger condition

**Choice:** Always run both proactive and hybrid recall, merge results with 2 reserved slots for hybrid-only matches

**Rationale:** Conditional fallback (trigger on low score count) proved unreliable — proactive returns high-scoring but irrelevant results for short/non-English queries, preventing the fallback from triggering. Always merging adds ~50-100ms but guarantees keyword matches are found. The 2 reserved slots ensure hybrid-only results aren't pushed out by the limit cap.

**Alternatives considered:**
- Conditional fallback (score >= 0.4 count) — failed in testing: proactive returned 3+ results with score >= 0.4 for "levelibéka" but none were relevant
- Fallback only on 0 results — too conservative, same problem

### Decision 2: Merge and dedup strategy

**Choice:** Append hybrid results after proactive results, deduplicate by content prefix (first 50 chars), assign synthetic score of 0.35 to hybrid-only results.

**Rationale:**
- Content prefix dedup matches the existing pattern in `proactive_and_format()` in the hook
- Synthetic score of 0.35 places hybrid results below strong proactive matches but above the hook's 0.3 cutoff
- Proactive results keep their original scores and appear first

**Alternatives considered:**
- Merge by memory ID — IDs differ between proactive and recall return formats
- Re-score hybrid results — no consistent scoring API available across both methods

### Decision 3: Implementation location

**Choice:** Modify `cmd_proactive` Python inline code in `bin/set-memory`

**Rationale:** Single location, no new files. The change is ~15 lines of Python within the existing inline script. All hooks benefit automatically since they call `set-memory proactive`.

## Risks / Trade-offs

**[Risk] Increased latency on fallback path** → Fallback adds one `recall()` call (~50-100ms). Only triggers when proactive fails, so happy path is unaffected. Acceptable tradeoff for correctness.

**[Risk] Hybrid results may include low-quality matches** → Mitigated by the hook's existing 0.3 score filter and the synthetic 0.35 score (only slightly above cutoff). The LLM further filters irrelevant context.

**[Risk] Duplicate results from both paths** → Mitigated by content-prefix dedup. Worst case: slightly different truncation shows near-duplicate, but this is cosmetic.
