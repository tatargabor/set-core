# Run #15 (2026-03-15) — COMPLETED — 8/8 merged

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

### 31. Uncommitted work guard false positive on framework-internal files
- **Type**: framework
- **Severity**: blocking (failed phase-1 change, blocked all 7 dependents)
- **Root cause**: `git_has_uncommitted_work()` in `git_utils.py` counted ALL dirty files including `.claude/` (loop-state, logs, activity.json), `.wt-tools/`, `CLAUDE.md`, and `openspec/changes/` (proposal.md). These are ALWAYS dirty during agent execution — written by Ralph loop, Claude Code session, and apply skill. The uncommitted work guard (introduced in `b0da40bf4`) didn't filter them, so every change would fail verify with "2 modified, 5 untracked" even when implementation was fully committed.
- **Fix**: [60d94c999] — Added `_FRAMEWORK_NOISE_PREFIXES` filter to `git_has_uncommitted_work()`. Framework-internal paths are excluded from the dirty check.
- **Deployed**: yes — wt-project init + worktree sync
- **Recurrence**: new (introduced in e2e-pipeline-hardening, never tested with real agent worktree)

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
