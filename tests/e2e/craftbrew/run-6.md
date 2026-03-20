# CraftBrew Run #6 — 2026-03-20

## Setup
- **set-core commit**: `b1179ccb6` (persist resolved model + 200K cleanup)
- **Project dir**: `/home/tg/.local/share/set-core/e2e-runs/craftbrew-run6`
- **Config**: max_parallel=2, default_model=opus-1m, smoke=pnpm build && pnpm test
- **Spec**: 24 files, 45 requirements, 9 domains → 15 changes planned

## Results

### Status: PARTIAL (8/15 merged, 1 stalled, 6 dep-blocked)

| Change | Status | Tokens | Notes |
|--------|--------|--------|-------|
| project-setup | merged | 37,983 | 0 retries |
| db-schema-seed-data | merged | 37,155 | Stalled once (Bug #30), reset+retry worked |
| email-service | merged | 55,559 | 0 retries, parallel with db-schema |
| layout-navigation | merged | 99,542 | 0 retries |
| user-auth-accounts | merged | 134,710 | merge-blocked → manual merge (Bug #28) |
| product-listing | merged | 88,612 | 0 retries |
| product-detail-search | merged | 70,242 | 0 retries |
| content-stories | merged | 63,738 | merge-blocked → manual merge (Bug #28) |
| cart-checkout | stalled | ~195K (1st), 0 (2nd) | 1st: review FAILED (build error from manual merge). 2nd: artifact loop (Bug #30) |
| promotions-coupons | pending | — | dep-blocked |
| reviews-wishlist | pending | — | dep-blocked |
| homepage | pending | — | dep-blocked |
| subscription-system | pending | — | dep-blocked |
| admin-panel | pending | — | dep-blocked |
| admin-content-moderation | pending | — | dep-blocked |

### Key Metrics
- **Wall clock**: ~9h (00:54–09:50, incl. stalls)
- **Active work time**: ~4h (excluding merge-blocked stalls)
- **Changes merged**: 8/15 (53%)
- **Sentinel interventions**: 3 (build fix, merge-blocked×2, artifact loop)
- **Total tokens**: ~587K
- **Verify retries**: 0 on all merged changes
- **Parallel dispatch**: worked (email+db, layout+auth, product-listing+content-stories)

## Bugs

### 28. Merger bypasses agent rebase — merge-blocked forever
- **Type**: framework
- **Severity**: blocking
- **Root cause**: When `set-merge --llm-resolve` fails without conflict markers (merge aborted cleanly), the code returned `merge-blocked` immediately via early return, skipping the agent-assisted rebase block. Also, all merge-tree/merge-base calls used `origin/main` refs which don't exist in local-only repos.
- **Fix**: `54687f0fc` + `0a3c4648b` — (1) fall-through to agent rebase instead of early return, (2) use local `main` ref everywhere
- **Deployed mid-run**: yes, but couldn't test because manual merge was already done
- **Recurrence**: new (caused merge-blocked in user-auth-accounts + content-stories)

### 29. Post-merge Prisma generate missing (recurrence)
- **Type**: app/framework
- **Severity**: blocking
- **Root cause**: After db-schema merge, `npx prisma generate` not run → build fails → `build_broken_on_main`
- **Fix**: `754167ef7` — added `post_merge_command: npx prisma generate` to scaffold config
- **Recurrence**: Run #5 same pattern

### 30. Agent artifact loop — implements artifacts but not code (recurrence)
- **Type**: framework
- **Severity**: blocking
- **Root cause**: Agent creates openspec artifacts (proposal, design, specs, tasks), outputs "Ready for `/opsx:apply`", but never starts implementation. The set-loop `done_criteria: openspec` treats artifact completion as "done" without checking for actual code changes. The Claude session may end after artifacts without triggering implementation.
- **Fix**: open — set-loop needs to detect "artifacts done but no impl" and inject a continuation prompt
- **Recurrence**: Run #5 (db-schema-seed-data), Run #6 (db-schema-seed-data, cart-checkout)

### 31. Dispatcher doesn't persist resolved model to state
- **Type**: framework
- **Severity**: noise (misleading logs)
- **Root cause**: `resolve_change_model()` returns `opus-1m` from config but never writes it back to state. Verifier reads `change.model` as None → `_context_window_for_model("")` → 200K. Logs show "2012% of 200K window" instead of "40% of 1M window".
- **Fix**: `b1179ccb6` — dispatcher writes impl_model to state after resolve
- **Recurrence**: new

## Conclusions

1. **opus-1m solved the context overflow**: Run #5's auth-and-accounts failed at 443K/200K. Run #6's user-auth-accounts succeeded at 134K — no context issues with 1M window.

2. **Parallel dispatch works well**: email+db, layout+auth, listing+stories all ran in parallel. max_parallel=2 is effective.

3. **0 verify retries on all 8 merged changes** — the verify gate is reliable when the build passes. The cart-checkout failures were all caused by a build error from manual merge, not by the verify gate itself.

4. **Bug #28 (merge-blocked) was the biggest blocker**: 2 changes stuck for hours because agent rebase never triggered. The fix is deployed but untested in production — Run #7 will validate.

5. **Bug #30 (artifact loop) recurred twice**: This is now the #1 priority framework fix. The agent creates artifacts but doesn't implement. The set-loop done criteria needs to check for actual code changes, not just artifact completion.

### Priority fixes for Run #7
1. **Bug #30 — artifact loop**: set-loop must detect "artifacts done, no impl" and continue
2. **Bug #28 verification**: confirm agent rebase works in production
3. **Auto-fix build on main**: when smoke fails after merge, dispatch a mini-agent to fix instead of blocking all dispatches
