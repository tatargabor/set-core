# Tasks: Context-Aware Merge

## Group 1: Scope injection

- [x] 1. In `merger.py` `merge_change()`, set `WT_MERGE_SCOPE` env var from `change.scope` before calling wt-merge [REQ: REQ-CAM-01]
- [x] 2. In `merger.py` retry merge path (L922), also set `WT_MERGE_SCOPE` [REQ: REQ-CAM-01]

## Group 2: Structural auto-resolve (pre-LLM)

- [x] 3. Add `auto_resolve_structural_conflicts()` function in `bin/wt-merge` — handles delete/modify (DU/UD), rename in tmp/.claude/ [REQ: REQ-CAM-02]
- [x] 4. Call `auto_resolve_structural_conflicts` after JSON auto-resolve and before `llm_resolve_conflicts` in the merge flow [REQ: REQ-CAM-02]
- [x] 5. After structural auto-resolve, re-check if conflicts remain — if none, skip LLM entirely [REQ: REQ-CAM-02]

## Group 3: LLM prompt enrichment

- [x] 6. Read `WT_MERGE_SCOPE` in `llm_resolve_conflicts()` and add "CONTEXT" section to prompt [REQ: REQ-CAM-01, REQ-CAM-05]
- [x] 7. Add branch history gathering: `git log --oneline source..target` (both directions, max 10 lines) [REQ: REQ-CAM-03]
- [x] 8. Extend existing `get_llm_hint()` with fallback path-based role hints (test, config, component, schema, page) [REQ: REQ-CAM-04]
- [x] 9. File role hints already injected per file via existing `get_llm_hint` call in prompt builder [REQ: REQ-CAM-04]
- [x] 10. Add "RESOLUTION STRATEGY" block to prompt: prefer source for feature, keep both for additive, target base for config [REQ: REQ-CAM-05]

## Group 4: Tests

- [x] 11. Verified: case patterns match test, config, component, schema, page paths correctly
- [x] 12. Verified: DU/UD status codes validated with real git merge conflicts
