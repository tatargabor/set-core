# Design: cross-change-review-learnings

## Context

The `review-findings.jsonl` already captures structured review findings per change. The `_persist_run_learnings()` in engine.py already has clustering logic (keyword clusters like no-auth, xss, no-rate-limit). We reuse both.

## Decisions

### D1: Dispatch-time injection into input.md, not loop prompt
The learnings are injected once at dispatch time into `input.md`. Not into the loop prompt (which regenerates every iteration — wasteful) and not into CLAUDE.md (which is the same token cost).

**Why:** input.md is read once by the agent at the start. The learnings are a static snapshot — they don't change mid-loop. Dispatch-time is the right moment.

### D2: Reuse engine.py cluster keywords
The `_CLUSTERS` dict in `_persist_run_learnings()` already maps keywords to cluster IDs. We extract this into a shared constant and reuse it in the dispatcher.

### D3: Compact format — headers + one-liners + reference
```
## Lessons from Prior Changes
These patterns caused failures in other changes during this run — avoid them:
- **No authentication**: API routes without auth middleware (auth-user-accounts, product-catalog)
- **XSS risk**: Using dangerouslySetInnerHTML without sanitization (content-email-bundles)

Full details: `wt/orchestration/review-findings.jsonl`
```
Max 15 lines. Only CRITICAL + HIGH. Clustered where possible, individual otherwise.

### D4: Exclude own change findings
Filter out `change_name == current_change` from the JSONL. The current change's own retry findings go through the existing `retry_context` mechanism.

## Files

| File | Change |
|------|--------|
| `lib/set_orch/dispatcher.py` | Add `review_learnings` to DispatchContext, `_build_review_learnings()` helper, render in `_build_input_content()` |
| `lib/set_orch/engine.py` | Extract `_CLUSTERS` to module-level constant (shared) |
| `tests/unit/test_dispatcher.py` | Test `_build_review_learnings()` with various JSONL inputs |
