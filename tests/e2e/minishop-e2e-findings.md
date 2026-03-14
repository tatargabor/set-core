# MiniShop E2E Findings

## Run #13 (2026-03-14)

### Status: IN PROGRESS — attempt 6 (3/6 merged, 2 running)

| Change | Status | Tokens | Retries | Build | Test | E2E | Review | Failure Reason |
|--------|--------|--------|---------|-------|------|-----|--------|----------------|
| test-infrastructure-setup | merged | 275k | 2 | pass | pass | n/a | pass | |
| products-page | merged | 142k | 1 | pass | pass | pass | pass | |
| cart-feature | merged | 408k→? | 2→5 | pass | pass | pass | pass | IDOR fixed on attempt 5 after web security rules deployed |
| admin-auth | running | 369k→? | 1→? | ? | ? | ? | ? | Retrying (att 6) with web auth-middleware rules |
| orders-checkout | running | 0→? | 0 | ? | ? | ? | ? | Newly dispatched (att 6, unblocked by cart-feature merge) |
| admin-products | pending | 0 | 0 | — | — | — | — | Blocked on admin-auth |

### Key Metrics
- **Wall clock**: ~63 min (22:08→23:11)
- **Changes merged**: 2/6 (33%)
- **Sentinel interventions**: 3 (partial resets + bug fix deploys)
- **Total tokens**: ~1.2M (275k + 142k + 408k + 369k)
- **Bugs found & fixed**: 1 framework bug (#20)
- **Verify retries**: 7 total (infra 2, products 1, cart 2, admin-auth 2)

### Framework Bugs Found

#### 20. Verify retry prompt misleading + done_criteria too weak
- **Type**: framework
- **Severity**: blocking
- **Root cause**: (1) Retry prompt for missing tests said "Add tests..." — agent interpreted as "only write tests" without implementing. (2) `done_criteria: "build"` meant if agent skipped implementation, existing build still passed → Ralph declared "done".
- **Fix**: [131d7d0ec] — Rewrote retry prompt to "IMPORTANT: First ensure ALL implementation is complete, then add tests". Changed `done_criteria` from `"build"` to `"test"` so agent's own tests must pass.
- **Recurrence**: new (first seen in run #13)

#### 21. Checkpoint status blocks poll loop — dead Ralph never detected
- **Type**: framework
- **Severity**: blocking
- **Root cause**: `engine.py` L303 `if state.status in ("paused", "checkpoint"): continue` — when monitor enters checkpoint, it skips `_poll_active_changes()`, so dead Ralph processes are never detected and verify/merge never completes. Monitor loops forever in checkpoint.
- **Fix**: [aa4296fc7] — Split checkpoint from paused. During checkpoint, still poll active changes and retry merge queue, only skip dispatch and advancement logic.
- **Recurrence**: new (first seen in run #13 attempt 5)
- **Impact**: admin-auth Ralph died but monitor was stuck in checkpoint for 16+ min without detecting it. Required sentinel restart to resume.

### Agent Quality Issues (Not Framework Bugs)

#### cart-feature: IDOR not fixed after 2 review retries
- Review gate correctly caught IDOR security bugs (removeFromCart/updateCartQuantity without session ownership checks)
- Retry prompt included review feedback with specific fix instructions
- Agent failed to add `sessionId` to `where` clauses in 2 retry attempts
- Framework working as designed — review gate prevented insecure code from merging

#### admin-auth: Missing middleware for auth redirect
- Agent implemented admin pages (login, register, dashboard) but never created `middleware.ts` for route protection
- E2E test "cold visit /admin redirects to /admin/login" timed out at 30s
- 15/16 E2E tests passed — only the redirect test failed
- Agent had 2 retries with E2E failure feedback but didn't add middleware

### Conclusions

1. **Review gate is valuable** — caught real IDOR vulnerabilities that would have shipped in earlier runs without code review. The 2-retry limit may be insufficient for security fixes; consider increasing `max_verify_retries` for review-critical failures specifically.

2. **Bug #20 fix validated** — cart-feature with the new retry prompt actually implemented all components (session, actions, cart page) + tests. Previous attempt (pre-fix) only wrote tests. The `done_criteria: "test"` change worked — agent couldn't declare "done" without passing its own tests.

3. **Cascade failure amplification** — 2 direct failures caused 2 cascade failures, turning a 2/6 into 2/6+2 cascade. The dependency chain (cart→checkout, admin-auth→admin-products) means phase 3+4 changes never got a chance.

4. **Token efficiency** — 1.2M tokens for 2/6 merged is poor compared to Run #4 (6/6 in similar token budget). The wasted tokens came from retry loops on unfixable agent issues.

5. **Comparison to previous runs**:
   - Run #4: 6/6 merged, 0 interventions, 1h42m — no review gate
   - Run #5: 8/8 merged, 3 interventions, 1h32m — no review gate
   - Run #13: 2/6 merged, 3 interventions, 1h03m — WITH review gate
   - The review gate is the key difference. It's catching real issues but the agents can't self-heal from review feedback.
