# Run #13 (2026-03-14)

### Status: COMPLETED — 6/6 merged (across 7 attempts)

| Change | Status | Tokens | Verify Retries | Build | Test | E2E | Review | Notes |
|--------|--------|--------|----------------|-------|------|-----|--------|-------|
| test-infrastructure-setup | merged | 275k | 2 | pass | pass | n/a | pass | Merged att 1 |
| products-page | merged | 142k | 1 | pass | pass | pass | pass | Merged att 1 |
| cart-feature | merged | 408k | 5 | pass | pass | pass | pass | IDOR fixed att 5 (web security rules) |
| admin-auth | merged | 369k | 2 | pass | pass | pass | pass | Merged att 7 (web auth-middleware rules) |
| orders-checkout | merged | 697k | 2 | pass | pass | pass | pass | Merged att 7 (manual merge-conflict resolution) |
| admin-products | merged | 287k | 1 | pass | pass | pass | pass | Merged att 7 |

### Key Metrics
- **Wall clock**: ~4h 24m (20:36→01:00), active agent time ~2h
- **Changes merged**: 6/6 (100%)
- **Attempts**: 7 (att 1-5 partial, att 6-7 completed remaining)
- **Sentinel interventions**: 5 (3 partial resets + bug fix deploys, 1 state reconstruction, 1 manual merge conflict resolution)
- **Total tokens**: ~2.18M (275k + 142k + 408k + 369k + 697k + 287k)
- **Bugs found & fixed**: 5 framework bugs (#20-#24)
- **Verify retries**: 13 total (infra 2, products 1, cart 5, admin-auth 2, orders-checkout 2, admin-products 1)
- **Merge retries**: 2 (orders-checkout 1 auto + 1 manual, admin-products 1)
- **Final test count**: 151 tests (5 suites), 31 E2E specs — all passing

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

#### 22. checkpoint_auto_approve directive parsed but never used
- **Type**: framework
- **Severity**: blocking
- **Root cause**: `checkpoint_auto_approve` was loaded into Directives and passed via `--checkpoint-auto-approve` CLI flag, but the engine loop never checked it. Checkpoints never auto-resolved, blocking dispatch indefinitely.
- **Fix**: [bb53d3a07] — When `checkpoint_auto_approve` is true, auto-resume from checkpoint to running after polling active changes.
- **Recurrence**: new (first seen in run #13 attempt 6)

#### 23. Checkpoint status not in bash resume list — state reinitialized on restart
- **Type**: framework
- **Severity**: critical (data loss)
- **Root cause**: `dispatcher.sh` L368 only resumes from `time_limit` or `stopped`. When sentinel restarts with state in `checkpoint` status, it falls through to `init_state()` which overwrites the state file, destroying all merged progress.
- **Fix**: [9422dc7ba] — Added `checkpoint` to the list of resumable statuses in the bash wrapper.
- **Recurrence**: new (first seen in run #13 attempt 6)
- **Impact**: Lost 4 merged changes (test-infrastructure-setup, products-page, cart-feature, admin-auth). Had to reconstruct state from git history.

#### 24. Merge-blocked by dirty generated files + leftover conflict markers
- **Type**: framework (merge pipeline)
- **Severity**: blocking
- **Root cause**: Two issues combined: (1) `.wt-tools/.last-memory-commit` modified in working tree blocked `git merge` with "local changes would be overwritten". (2) `pnpm-lock.yaml` had 11 leftover conflict markers from the admin-products merge that were never resolved, causing subsequent merges to fail. The auto-merge pipeline (`wt-merge`) doesn't handle these generated file conflicts.
- **Fix**: Manual resolution — `git checkout --ours` for runtime state files (activity.json, loop-state.json, ralph-terminal.pid, .last-memory-commit), `pnpm install --no-frozen-lockfile` to regenerate lockfile. No code fix committed — this is a known limitation of the merge pipeline (see also Bug #8 from earlier runs with pnpm-lock conflicts).
- **Recurrence**: recurring (pnpm-lock.yaml conflicts seen in runs #3, #8, #13)
- **Impact**: orders-checkout passed all gates (138 tests, 31 E2E, build, review) but couldn't merge. Required sentinel-level manual intervention.

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

1. **6/6 achieved — with heavy sentinel involvement.** All changes eventually merged, but required 7 attempts, 5 framework bug fixes, and manual merge conflict resolution. This is the first run with the review gate that achieved 100% merge rate.

2. **Review gate + web security rules = validated.** Cart-feature's IDOR was caught by review, then fixed after deploying `.claude/rules/web/security-patterns.md`. Admin-auth's missing middleware was fixed after deploying `.claude/rules/web/auth-middleware.md`. The rules-as-context approach works — agents follow the patterns when given explicit rules in retry prompts.

3. **Checkpoint architecture was fundamentally broken.** Bugs #21-#23 revealed that "checkpoint" status was added as a concept but never integrated across the three layers (Python engine, CLI forwarding, bash resume). Four separate fixes were needed. Bug #23 caused data loss — the most severe issue in any E2E run so far.

4. **Merge pipeline fragility persists (Bug #24).** pnpm-lock.yaml conflicts have occurred in runs #3, #8, and #13. The auto-merge pipeline needs generated-file-aware conflict resolution (regenerate lockfile instead of attempting text merge). This is the single most common manual intervention across all runs.

5. **Token efficiency improved over mid-run.** Final 2.18M tokens for 6/6 merged is reasonable — comparable to Run #4 (6/6, 2.7M). The early waste came from retry loops before web security rules were deployed, not from the review gate itself.

6. **Comparison to previous runs**:
   - Run #4: 6/6 merged, 0 interventions, 1h42m, 2.7M tokens — no review gate
   - Run #5: 8/8 merged, 3 interventions, 1h32m — no review gate
   - Run #13: 6/6 merged, 5 interventions, ~4h24m, 2.18M tokens — WITH review gate + web security rules
   - The review gate adds wall clock time (more retries) but catches real security issues. Web security rules significantly improve agent self-healing on security feedback.

7. **Priority fixes for next run**:
   - P0: Auto-resolve pnpm-lock.yaml conflicts in merge pipeline (regenerate, not text merge)
   - P1: Add `.wt-tools/` and `.claude/` runtime files to `.gitignore` in consumer projects to prevent merge-blocking dirty state
   - P2: Increase `max_verify_retries` to 3 for review-failed changes (security fixes often need more iterations)
