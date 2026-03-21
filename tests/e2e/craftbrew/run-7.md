# CraftBrew Run #7 — 2026-03-20/21

## Final Run Report

### Status: COMPLETED (14/14 merged)

| Change | Phase | Status | Tokens | Time | Notes |
|--------|-------|--------|--------|------|-------|
| project-setup | 1 | merged | 28K | ~20m | Bug #31 hit on first try; fixed and retried |
| database-schema | 1 | merged | 89K | ~30m | 2 verify retries (build + review) |
| layout-shell | 1 | merged | 61K | ~15m | Clean merge, no retries |
| auth-and-accounts | 1 | merged | 123K | ~90m | 4 verify retries; redispatch #2 due to merge conflicts |
| product-catalog-list | 2 | merged | 100K | ~25m | Bug #32 hit (dirty files); fixed and retried |
| product-detail-and-search | 2 | merged | 6K | ~10m | Very efficient, no retries |
| content-stories | 2 | merged | 76K | ~15m | Clean |
| seed-data | 2 | merged | 99K | ~20m | Clean |
| cart-checkout | 3 | merged | 114K | ~40m | 1 verify retry; stalled once |
| promotions-and-email | 3 | merged | ~75K | ~20m | Clean (token counter missed by monitor) |
| subscription-management | 4 | merged | 135K | ~30m | Integration-failed once (transient git error) |
| reviews-wishlist-homepage | 4 | merged | 144K | ~25m | 1 verify retry |
| admin-catalog-orders | 5 | merged | ~95K | ~30m | Clean |
| admin-operations | 5 | merged | 113K | ~35m | 2 verify retries |

### Key Metrics
- **Wall clock**: ~7h 30m (22:59 → 06:20, including manual interventions)
- **Changes merged**: 14/14 (100%)
- **Sentinel interventions**: 8 (manual lock cleanups, state resets, worktree removal)
- **Total tokens**: ~1.26M (estimated from per-change tracking)
- **Bugs found & fixed**: 2 framework bugs (Bug #31, Bug #32)
- **Verify retries**: ~18 total across all changes

### Framework Bugs Found

### 28. `origin/main` ref fails in local-only repos (integration merge)
- **Type**: framework
- **Severity**: blocking
- **Root cause**: `verifier.py` and `loop_tasks.py` hardcoded `origin/<main>` for integration merges. In local-only repos (E2E tests), there's no origin remote.
- **Fix**: [82bfe9955] — fall back to local `<main>` ref when `git fetch origin` fails
- **Deployed**: yes, verified on 2nd merge (layout-shell)
- **Recurrence**: new (similar to Run #5 Bug #24 but different code path)

### 29. Dirty files block integration merge
- **Type**: framework
- **Severity**: blocking
- **Root cause**: Agents leave uncommitted files (`.claude/reflection.md`, `CLAUDE.md`) in worktree. `git merge` refuses with "Your local changes would be overwritten".
- **Fix**: [dac800bac] — stash dirty files before merge, pop after (all exit paths)
- **Deployed**: yes, verified on product-catalog-list retry
- **Recurrence**: new

### Observations (not bugs)

1. **Orchestrator stale lock crash loop** — When orchestrator exits, `orchestrator.lock` isn't always cleaned up. Sentinel restart hits "Another orchestrator already running" and enters rapid crash loop. Required ~5 manual lock cleanups during the run. Potential Bug #33 for future fix.

2. **Sentinel stuck detection during verify gate** — The verify gate review process takes >30min sometimes. Sentinel threshold is 1800s (30min), causing false stuck detection + kill. The monitor watchdog also triggers "no progress" warnings. Not harmful (sentinel auto-restarts) but noisy.

3. **Dependency cascade deadlock** — `auth-and-accounts` failing blocked 6 dependent changes. Required manual intervention to redispatch on clean branch. Known limitation (Bug #26).

4. **State overwrite on restart** — At T+445m, orchestrator restart said "Starting orchestration..." instead of "Resuming..." and created a fresh plan, losing 13 merged changes in state. The git history was intact (all 14 changes merged on main). Root cause: likely the state file was in an inconsistent state during the restart.

5. **Token counter not updating** — Several changes showed tokens=0 throughout their lifecycle despite active implementation. The monitor's token tracking relies on the agent loop completion event, which doesn't fire during artifact creation phase.

### Functional Gap Analysis (post-run audit)

6. **Decomposer narrows scope to one example** — The `product-catalog-list` change scope correctly states "browse products across categories (coffees, equipment, merch, bundles)" but the artifact creation agent generated tasks only for `/coffees/page.tsx`. The other 3 category listing pages were never tasked. The agent treats the first category as representative and considers the scope done. **Fix:** `web-route-completeness-rules` change — Pattern A (Category Listing Completeness) review rule.

7. **Phantom task completion (returns flow)** — The `cart-checkout` change has return-request tasks (8.1–8.3, 9.2, 10.6) marked `[x]` done in tasks.md, but `src/app/api/returns/route.ts` and the return request UI don't exist. The agent marked tasks complete without creating the referenced files. The verify gate checks task checkboxes, not file existence. **Fix:** `web-route-completeness-rules` change — Pattern C (Task-File Correlation) review rule + verification rule in set-project-web.

8. **Admin page gaps** — Spec mentions admin management for returns but no `/admin/returns/page.tsx` exists. Same pattern as storefront category gaps but in the admin subtree. **Fix:** `web-route-completeness-rules` change — Pattern D (Admin Resource Completeness).

### Conclusions
1. **14/14 merged — massive improvement over Run #6 (8/15).** The verify/merge pipeline fixes (review rules, merge heartbeats, review diff prioritization) from the 11 commits since Run #6 made a huge difference.
2. **Bug #31 and #32 were the key blockers.** Both were integration merge issues — the new integrate-then-verify pipeline exposed git edge cases (no remote, dirty files) that the old merge-on-main path didn't hit.
3. **Stale lock files are the biggest remaining annoyance.** ~5 manual interventions were just lock cleanup. This should be fixed with proper lock cleanup on exit (atexit handler or PID-based lock validation).
4. **auth-and-accounts was the bottleneck.** 4 verify retries + redispatch consumed ~90min of serial time. All 6 dependent changes waited. Better parallelization (dispatch deps-met changes even if some deps are in review cycle) could help.
5. **Review gate is thorough but expensive.** Every M-complexity change needed 1-4 review retries. The security review catches real issues (IDOR, XSS, missing auth) but the churn adds significant wall clock time.
