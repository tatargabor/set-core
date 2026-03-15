# MiniShop E2E Findings

## Run #15 (2026-03-15) — COMPLETED — 8/8 merged

### Run Results

| Change | Status | Tokens | VR | MR | Manual? | Notes |
|--------|--------|--------|----|----|---------|-------|
| test-infrastructure-setup | merged | 8k | 0 | 1 | no | Reused from master (trivial) |
| database-schema | merged | 1,033k | 2 | 1 | no | 2 verify retries (build issues) |
| app-foundation | merged | 920k | 2 | 1 | no | 2 verify retries |
| products-page | merged | 389k | 0 | 6 | YES | pkg.json merge conflict — manual deep-merge |
| admin-auth | merged | 210k | 0 | 1 | no | Clean run |
| cart-feature | merged | 576k | 0 | 1 | YES | Bug #34 stall + Bug #36 uncommitted work (2 manual commits) |
| admin-products | merged | 1,412k | 0 | 6 | YES | pkg.json merge conflict — manual deep-merge |
| orders-checkout | merged | 1,296k | 1 | 4 | YES | Log chain only conflict — trivial manual merge |

### Key Metrics
- **Wall clock**: ~2h 45m (17:12→19:57)
- **Changes merged**: 8/8 (100%)
- **Total tokens**: 5,279k (input=4,919k, output=360k, cache_read=113,176k, cache_create=7,627k)
- **Sentinel interventions**: 5 (products-page merge, cart-feature stall+commits, orchestrator restart, admin-products merge, orders-checkout merge)
- **Bugs found**: #31 (fixed+deployed), #32-#36 (noted for future)
- **Commits**: 43 total in minishop repo

### Conclusions

1. **8/8 merged — first full completion of expanded minishop spec.** All 8 changes (including new EAV product variants) merged successfully. This validates the full pipeline with design bridge, gate profiles, and uncommitted work guard.

2. **Bug #31 fixed mid-run.** The uncommitted work guard false positive on framework files was the only deployed fix. All other bugs (#32-#36) are noted for future runs.

3. **Package.json merge conflict remains the #1 issue.** products-page (mr=6) and admin-products (mr=6) both hit the same pattern: LLM merge resolver can't handle package.json + pnpm-lock.yaml. Manual deep-merge protocol works but requires sentinel intervention every time. Recurring across runs #3, #8, #13, #14, #15.

4. **Bug #34 (sentinel/orchestrator coordination) caused the most waste.** cart-feature burned 568k wasted tokens because sentinel removed worktrees while orchestrator was alive, crashing Ralph terminals. The stall→manual reset→redispatch cycle is expensive.

5. **Bug #36 (uncommitted work guard) needs auto-commit.** cart-feature required 2 manual commit rounds (12 files, 754 insertions) because the agent created files but didn't commit them before verify. Auto-commit before verify would eliminate this.

6. **Comparison to previous runs**:
   - Run #13: 6/6, 5 interventions, 4h24m, 2.18M tokens
   - Run #14: 2/7 (stopped), 0 interventions, 45m, 676k tokens
   - Run #15: 8/8, 5 interventions, 2h45m, 5.28M tokens
   - Token efficiency: 660k/change vs 363k/change (run #13) — higher due to merge retries and Bug #34 waste

7. **Priority fixes for Run #16**:
   - **P0**: Bug #36 — Auto-commit before verify gate (eliminates manual uncommitted work interventions)
   - **P0**: Package.json merge — Always regenerate pnpm-lock.yaml instead of text merge; use jq deep-merge for package.json
   - **P1**: Bug #34 — Sentinel must kill orchestrator before removing worktrees
   - **P1**: Bug #33 — Add `post_dispatch_command: "pnpm install"` for worktree setup
   - **P2**: Bug #32 — Update apply prompt to use direct file reads instead of nonexistent CLI commands
   - **P2**: Bug #35 — Log rotation on redispatch

### Framework Bugs Found This Run

### 32. Agent wastes iterations on nonexistent `openspec status` CLI commands
- **Type**: framework (agent prompt issue)
- **Severity**: noise (wastes ~6 tool calls before fallback to direct file read)
- **Root cause**: The agent's apply prompt references `openspec status --change` and `openspec instructions apply` which don't exist in the pinned openspec v1.1.1. The agent retries 6 times before falling back to reading artifacts directly.
- **Fix (TODO)**: Update the apply skill prompt to read artifacts directly (Glob+Read) instead of suggesting nonexistent CLI commands. We only use openspec for `new change`, `list --json`, `--version`.
- **Deployed**: no — noted for next run
- **Recurrence**: likely every run

### 33. Agent can't run `pnpm test` — node_modules not installed in worktree
- **Type**: framework (post-merge deps missing)
- **Severity**: blocking (agent retries pnpm test 5x, all fail)
- **Root cause**: `test-infrastructure-setup` created `package.json` + `pnpm-lock.yaml` and committed them. After merge to master, new worktrees (`database-schema`) get these files but NOT `node_modules/` (gitignored). The agent needs to `pnpm install` first but the apply prompt doesn't instruct it. This is the same root cause as **Bug #29** from Run #14.
- **Fix (TODO)**: Add `post_dispatch_command: "pnpm install"` to orchestration config, OR have the dispatcher run `pnpm install` in the worktree after creation, OR add it to the agent prompt as a first step.
- **Deployed**: no — noted for next run
- **Recurrence**: Bug #29 regression confirmed

### 34. Sentinel worktree removal crashes live orchestrator's Ralph terminal
- **Type**: framework (sentinel/orchestrator coordination)
- **Severity**: blocking (cart-feature stalled indefinitely, required manual reset)
- **Root cause**: Sentinel removed worktrees for `cart-feature` and `admin-products` while the old orchestrator (PID 123440) was still alive. The orchestrator had spawned Ralph terminals in those worktrees. When the worktree directories were deleted, the Claude sessions inside the terminals crashed (`error: The current working directory was deleted`). The orchestrator detected `stalled` but never auto-recovered (no kill+redispatch logic for stalled changes with dead terminals).
- **Fix (TODO)**: Two issues: (1) Sentinel must kill orchestrator before removing worktrees — never modify live orchestrator's resources. (2) Orchestrator's stall handler should detect dead terminal PIDs and auto-redispatch instead of staying in `stalled` forever.
- **Deployed**: no — manual intervention (kill Ralph, reset to pending, remove worktree+branch)
- **Recurrence**: new (sentinel coordination issue)

### 35. Ralph terminal PID reuse — chain log contains output from deleted worktrees
- **Type**: framework (log contamination)
- **Severity**: noise (confusing diagnostics)
- **Root cause**: cart-feature's `ralph-iter-001-chain.log` contained completion messages from admin-auth ("All 20 tests passing, 4 suites") followed by "current working directory was deleted". The Ralph terminal was originally spawned for a different change's worktree context. When reused for cart-feature, the log file carried over stale output.
- **Fix (TODO)**: Truncate/rotate log files when dispatching to an existing worktree. Or ensure each dispatch gets a fresh terminal.
- **Deployed**: no — noted for next run
- **Recurrence**: new

### 36. Uncommitted work guard retries with full redispatch instead of targeted fix
- **Type**: framework (verifier.py)
- **Severity**: waste (burns entire agent session per retry)
- **Root cause**: When `git_has_uncommitted_work()` finds real uncommitted files (e.g. `e2e/cart.spec.ts`, `tests/cart.test.ts`), the verifier sets `retry_context` with "commit or remove all uncommitted files" and redispatches a fresh agent. But the new agent creates files and also doesn't commit — repeating the same pattern. A full agent redispatch for uncommitted files is overkill.
- **Fix (TODO)**: Before redispatch, auto-commit remaining files: `git add . && git commit -m "chore: commit remaining work"` in the worktree. Then re-run verify without spawning a new agent. Only redispatch if verify still fails after auto-commit.
- **Deployed**: no — noted for next run
- **Recurrence**: new (guard is new from this run)

### 31. Uncommitted work guard false positive on framework-internal files
- **Type**: framework
- **Severity**: blocking (failed phase-1 change, blocked all 7 dependents)
- **Root cause**: `git_has_uncommitted_work()` in `git_utils.py` counted ALL dirty files including `.claude/` (loop-state, logs, activity.json), `.wt-tools/`, `CLAUDE.md`, and `openspec/changes/` (proposal.md). These are ALWAYS dirty during agent execution — written by Ralph loop, Claude Code session, and apply skill. The uncommitted work guard (introduced in `b0da40bf4`) didn't filter them, so every change would fail verify with "2 modified, 5 untracked" even when implementation was fully committed.
- **Fix**: [60d94c999] — Added `_FRAMEWORK_NOISE_PREFIXES` filter to `git_has_uncommitted_work()`. Framework-internal paths are excluded from the dirty check.
- **Deployed**: yes — wt-project init + worktree sync
- **Recurrence**: new (introduced in e2e-pipeline-hardening, never tested with real agent worktree)

---

## Run #14 (2026-03-15) — COMPLETED

### Pre-run Bugs Found (planning phase)

#### 25. bridge.sh log_warn/log_info undefined — crashes design fetch
- **Type**: framework
- **Severity**: blocking (planner crash loop → sentinel rapid_crashes 5/5)
- **Root cause**: `bridge.sh` used `log_warn`/`log_info` which don't exist. When sourced standalone from Python subprocess (without `wt-common.sh`), `command not found` error crashed `check_design_mcp_health`, causing planner RuntimeError. The `2>/dev/null` on the bash bridge source swallowed the error from the orchestration log.
- **Fix**: [118223a05] — Added fallback log functions at top of bridge.sh (`info`/`warn`/`error` no-ops if not already defined), renamed all `log_warn`→`warn`, `log_info`→`info`.
- **Recurrence**: new (introduced during bash→Python migration, never tested standalone)

#### 26. Design MCP health check needs run_claude PTY — hangs from Python
- **Type**: framework
- **Severity**: blocking (planner hangs indefinitely)
- **Root cause**: `check_design_mcp_health()` calls `run_claude` (a bash function from `wt-common.sh` that uses `script -f` PTY wrapper). When called from Python subprocess via `bash -c 'source bridge.sh'`, `run_claude` is undefined (rc=127). Sourcing `wt-common.sh` doesn't work either — it has interactive side effects that hang the subprocess.
- **Fix**: [a0a9f2823] → [3bca71c13] — Skip health check from Python planner, go straight to `setup_design_bridge + fetch_design_snapshot`. The fetch will fail fast if MCP isn't working.
- **Recurrence**: new (same migration gap as #25)

#### 27. Figma URL format wrong — /design/ instead of /make/
- **Type**: configuration
- **Severity**: blocking (MCP fetch hangs/times out with /design/ URLs)
- **Root cause**: Scaffold spec used `/design/` URL format. Figma MCP requires `/make/` format for proper API access.
- **Fix**: [71259c611] — Updated `tests/e2e/scaffold/docs/v1-minishop.md` to use `/make/` URL.
- **Recurrence**: new

#### 28. All subprocess timeouts were 300s — too aggressive
- **Type**: framework
- **Severity**: noise (causes unnecessary restarts)
- **Root cause**: Every `run_command`/`run_claude` call in the orchestration pipeline had `timeout=300` (5 min). LLM calls (planner, auditor, replan) and design fetch can legitimately take 10-30 min. The sentinel and watchdog handle stuck detection — tight subprocess timeouts just cause false failures.
- **Fix**: [4946757ee] — LLM calls → 1800s (30min), build/test/merge/install → 600s (10min).
- **Recurrence**: new (timeout values were set during initial implementation, never calibrated against E2E runs)

### Runtime Bugs Found

#### 29. Post-merge deps install uses HEAD~1 diff — misses package.json from multi-commit merges
- **Type**: framework (merger.py)
- **Severity**: causes smoke failure (non-blocking — change still merges)
- **Root cause**: `_post_merge_deps_install()` (merger.py:572-576) checks `git diff HEAD~1 --name-only` for `package.json`. But wt-merge creates multiple commits (impl + archive), so HEAD~1 only shows the archive commit diff. The actual `package.json` is in an earlier commit (e.g. HEAD~3). Result: `pnpm install` never runs → `node_modules` missing → smoke `pnpm test` fails with "node_modules missing, did you mean to install?"
- **Fix**: Not yet committed. Should diff against merge-base (pre-merge tag or saved ref), not HEAD~1. Alternative: always install if `package.json` exists and `node_modules/` doesn't.
- **Recurrence**: new (likely present since merger.py migration but masked when smoke wasn't configured)
- **Impact**: Both test-infrastructure-setup and products-page got smoke=fail despite all other gates passing.

#### 30. spec_coverage_result=fail causes unnecessary verify retry
- **Type**: framework (verifier.py)
- **Severity**: waste (extra 81k tokens for products-page retry)
- **Root cause**: products-page passed test/build/review on vr=1 retry, but `spec_coverage_result=fail` triggered a second redispatch (vr=2). The agent on vr=2 added minimal changes and got `spec=soft-pass`. This retry burned 81k tokens (406k total vs run13's 142k for same change). spec_coverage is useful but should not trigger full redispatch — at most a targeted fix prompt.
- **Fix**: Not yet committed. Consider: (1) make spec_coverage a warning not a retry trigger, or (2) only retry once for spec coverage specifically with a focused prompt.
- **Recurrence**: new (spec_coverage gate is new since run13)

### Run Results (partial — stopped after 2/7 merged)

| Change | Status | Tokens | Verify Retries | Build | Test | Review | Smoke | Notes |
|--------|--------|--------|----------------|-------|------|--------|-------|-------|
| test-infrastructure-setup | merged | 231k | 0 | pass | pass | pass | fail | Bug #29: no node_modules for smoke |
| products-page | merged | 406k | 2 | pass | pass | pass | fail | vr=1 build fail (prerender), vr=2 spec_coverage |
| cart-feature | running (killed) | 15k | 0 | - | - | - | - | Killed at phase 3 start |
| admin-auth | running (killed) | 22k | 0 | - | - | - | - | Killed at phase 3 start |
| orders-checkout | pending | - | - | - | - | - | - | |
| admin-products | pending | - | - | - | - | - | - | |
| playwright-e2e | pending | - | - | - | - | - | - | |

### Key Metrics (partial)
- **Wall clock**: ~45min (11:29→12:15), stopped intentionally after phase 2
- **Changes merged**: 2/7 (stopped to analyze)
- **Sentinel interventions**: 0 (clean run!)
- **Total tokens**: 676k (231k + 406k + 15k + 22k + misc)
- **Bugs found**: 2 runtime (#29, #30) + 4 pre-run (#25-#28)
- **Framework health**: digest/decompose/dispatch/verify/merge all working. No crashes, no stuck states.

### Conclusions

1. **Pre-run fixes validated.** Bugs #25-#28 (bridge.sh, MCP health, Figma URL, timeouts) all resolved. No planner crashes, no MCP hangs, design snapshot fetched successfully (9433 bytes).

2. **Zero sentinel interventions.** First run14 attempt was clean — no crash loops, no stuck states, no manual resets. This is a major improvement over run13 (5 interventions).

3. **Bug #29 — smoke install gap.** `_post_merge_deps_install` needs to diff against merge-base, not HEAD~1. Both merged changes got smoke=fail because node_modules was never installed on main. Non-blocking but should be fixed.

4. **Bug #30 — spec_coverage retry is too expensive.** products-page burned 81k extra tokens (406k total vs 142k in run13) for a spec_coverage retry that barely changed anything. The gate works but shouldn't trigger a full agent redispatch.

5. **Design integration works end-to-end.** Figma MCP → design-snapshot.md → planner context → agent dispatch. The snapshot was cached and available for all changes. However, products-page used 406k tokens (vs 142k in run13) — the design context adds overhead.

6. **Comparison to run13 (same 2 changes)**:
   - test-infrastructure-setup: 231k vs 275k (run13) — improved
   - products-page: 406k vs 142k (run13) — worse (2 retries + design context)
   - Both merged vs both merged — same success rate

### Priority Fixes Before Run15
- **P0**: Bug #29 — Fix `_post_merge_deps_install` to use merge-base diff or always-install-if-missing
- **P1**: Bug #30 — Make spec_coverage a soft gate (warning, not retry trigger) or limit to 1 retry with focused prompt
- **P2**: Investigate products-page token inflation (406k vs 142k) — is design context too verbose?

### Status: Stopped after phase 2 for analysis

---

## Run #13 (2026-03-14)

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
