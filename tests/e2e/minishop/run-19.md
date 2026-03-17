# MiniShop E2E Run #19

**Date**: 2026-03-17
**wt-tools commit**: `957d125d9` (includes mid-run fixes)
**Project dir**: `/tmp/minishop-run5`
**Duration**: ~4h (14:45–18:46)

## Final Run Report

### Status: COMPLETED — 9/12 merged

| Change | Complexity | Status | Tokens | Retries | Notes |
|--------|-----------|--------|--------|---------|-------|
| project-infrastructure | M | merged | 207K | 0 | Clean first merge |
| auth-foundation | S | merged | 115K | 2 | Tailwind v3/v4 fix (app), review template crash (framework) |
| storefront-layout | S | merged | 253K | 0 | Clean |
| product-catalog | S | merged | 310K | 0 | Prisma DB prerender fix needed |
| product-detail | S | merged | 384K | 1 | Prisma table missing — retry fixed |
| admin-dashboard-list | M | merged | 693K | 0 | Chain session stuck, manual redispatch + manual merge needed |
| cart-core | S | merged | 485K | 2 | Scope check fail pattern (artifacts first) |
| cart-management | S | FAILED | 513K | 3 | Scope check + retry exhaustion |
| order-placement | S | merged | 328K | 1 | Review:critical (IDOR) — retry fixed security |
| order-views | S | FAILED | 310K | 3 | Review:critical (IDOR) — retry exhaustion |
| admin-crud | M | merged | 577K | 3 | Review:critical (IDOR) — manual merge needed (orchestrator stuck) |
| responsive-polish | S | pending | 0 | 0 | Blocked by cart-management (failed) |

### Key Metrics
- **Wall clock**: ~4h
- **Changes merged**: 9/12 (75%)
- **Sentinel interventions**: 2 manual merges (admin-dashboard-list, admin-crud) + multiple state fixes
- **Total tokens**: 4.1M
- **Bugs found & fixed**: 2 (Bug #49, Bug #51)
- **Bugs found (unfixed)**: 2 (Bug #50, Bug #52)
- **Verify retries**: 18 total across all changes

### vs Run #18
- **Run #18**: 1/10 merged (INTERRUPTED), ~3h, ~5M tokens, 6+ interventions
- **Run #19**: 9/12 merged (COMPLETED), ~4h, 4.1M tokens, 2 interventions
- **Improvement**: Massive — Bug #51 fix (review template) was the key unlock

## Bugs Found

### 49. Decompose stderr swallowed by 2>/dev/null
- **Type**: framework
- **Severity**: blocking (decompose phase)
- **Root cause**: `planner.sh` line 188 used `2>/dev/null` on `wt-orch-core plan run`, hiding all error details
- **Fix**: `7551be1f5` — capture stderr to temp file, include in error message
- **Recurrence**: new

### 50. State reconstruction loses merged status
- **Type**: framework
- **Severity**: high (requires manual state fix after every orchestrator crash)
- **Root cause**: Sentinel `reconstruct_state_from_events()` replays STATE_CHANGE events, but the Python monitor doesn't emit STATE_CHANGE events to the events.jsonl. Result: all changes reconstructed as `running` regardless of actual status.
- **Fix**: NOT FIXED — manually corrected auth-foundation multiple times during run
- **Recurrence**: new (the Python monitor migration introduced this — bash layer used to emit events)

### 51. Review template f-string crash (MAJOR BLOCKER)
- **Type**: framework
- **Severity**: blocking (ALL verify gates)
- **Root cause**: `templates.py:222` had unescaped `{ id: cartItemId, sessionId: getSessionId() }` inside an f-string. Python interpreted `id` as a variable → NameError. This crashed every code review attempt.
- **Fix**: `957d125d9` — escape braces with `{{ }}`
- **Recurrence**: new (introduced during impl-quality-runtime change)

### 52. Orchestrator stuck during merge/archive — git_failed spam
- **Type**: framework
- **Severity**: medium (requires manual wt-merge intervention)
- **Root cause**: After verify gates pass, the merge/archive step emits many `git_failed` warnings (from `run_git` calls in merger/archiver). These don't emit events, causing the sentinel stuck detector to kill the orchestrator mid-merge. The change stays in `verifying` state indefinitely.
- **Pattern**: verify pass → merge attempt → git_failed spam → no events → sentinel kills → restart → same cycle
- **Fix**: NOT FIXED — manually merged admin-dashboard-list and admin-crud via `wt-merge`
- **Recurrence**: new (likely related to Python merger not handling worktree git operations correctly)

## Conclusions

1. **Bug #51 was the key blocker** — once fixed (957d125d9), the pipeline ran smoothly. All verify gates worked, security reviews caught real IDOR issues, and agents self-corrected.

2. **Bug #50 (state reconstruction)** needs urgent fix — the Python monitor must emit STATE_CHANGE events to orchestration-state-events.jsonl so the sentinel can reconstruct correctly after crashes.

3. **Bug #52 (merge stuck)** is the next priority — the orchestrator hangs during merge/archive with git_failed spam, requiring manual `wt-merge` intervention. This affected 2/9 successful merges.

4. **Scope check fail pattern** wastes tokens — agents create OpenSpec artifacts (proposal, design, specs, tasks) on first dispatch, then scope_check rejects them as "only artifact/bootstrap files". This burns a full retry cycle (~100K tokens) per change. The dispatch prompt should explicitly instruct agents to IMPLEMENT, not just create artifacts.

5. **Security review working well** — the code review gate correctly caught IDOR vulnerabilities in order-placement, order-views, and admin-crud. The retry agents fixed the security issues in 2/3 cases.

6. **Token efficiency**: 4.1M total for 9 merged changes = ~456K/change average. This is within the M complexity range but higher than ideal for S changes due to retry overhead.
