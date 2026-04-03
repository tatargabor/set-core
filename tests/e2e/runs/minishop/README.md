# MiniShop E2E Run History

Summary of orchestration E2E runs against the MiniShop test project.

| Run | Date | Result | Changes | Tokens | Time | Interventions | Bugs | Notes |
|-----|------|--------|---------|--------|------|---------------|------|-------|
| [#13](run-13.md) | 2026-03-14 | 6/6 merged | 6 | 2.18M | 4h24m | 5 | #20-#24 | First run with review gate |
| [#14](run-14.md) | 2026-03-15 | 2/7 stopped | 7 | 676k | 45m | 0 | #25-#30 | Stopped for analysis after phase 2 |
| [#15](run-15.md) | 2026-03-15 | 8/8 merged | 8 | 5.28M | 2h45m | 5 | #31-#36 | First full expanded spec completion |
| [#16](run-16.md) | 2026-03-16 | 11/11 merged | 11 | 4.6M | 3h13m | 5 | #37-#41 | Full 40-req spec, 100% completion |
| [#17](run-17.md) | 2026-03-17 | 11/11 merged | 11 | ~4.5M | 5h17m | 11 | #42-#44 | Bug #37 root cause fixed (node_modules), Bug #38 partial fix |
| #18 | 2026-03-17 | 1/10 interrupted | 10 | ~5M | ~3h | 6+ | #45-#48 | Bug #51 review template blocker |
| [#19](run-19.md) | 2026-03-17 | 11/12 merged | 12 | ~5M | ~8h | 4 | #49-#53 | Bug #51+#53 fixes → 11/12 (92%) with retry |
| #16* | 2026-04-03 | 6/6 merged | 6 | 333M | 1h10m | 1 | #54 | Divergence run A — context breakdown enabled, sentinel self-healed engine.sh crash |
| #17* | 2026-04-03 | 6/6 merged | 6 | — | — | 2 | — | Divergence run B — API limit hit during auth-navigation, auto-recovered |

\* Runs #16-#17 (April) are a new numbering series for divergence comparison. See [run-16-vs-17.md](run-16-vs-17.md).

## Latest Divergence Comparison

**[minishop-run16 vs minishop-run17](run-16-vs-17.md)** — Score: **83/100** (structurally equivalent)

| Metric | Score | Notes |
|--------|-------|-------|
| Schema equivalence | 100% | All 9 models identical |
| Route coverage | 83% | 20 common, 2 unique each (API naming) |
| Convention compliance | 100% | Route groups, prisma.ts, utils.ts all correct |
| Dependency set | 81% | 30 common packages |
| Functional categories | 73% | UI primitives diverge (shadcn import vs inline) |
| Template compliance | 75%/88% | run17 better (7/8 unchanged vs 5/8) |
| E2E test naming | 18% overlap | Different names, similar coverage |

**Key divergence drivers**: UI primitive import strategy (shadcn vs none), unit test presence (3 vs 0), e2e file naming convention.

## Bug Index

| # | Summary | Run | Status |
|---|---------|-----|--------|
| 20 | Verify retry prompt misleading + done_criteria too weak | #13 | fixed |
| 21 | Checkpoint status blocks poll loop | #13 | fixed |
| 22 | checkpoint_auto_approve never used | #13 | fixed |
| 23 | Checkpoint status not in bash resume list (data loss) | #13 | fixed |
| 24 | Merge-blocked by dirty generated files + pnpm-lock conflicts | #13 | fixed (`eec894bcb`) |
| 25 | bridge.sh log functions undefined | #14 | fixed |
| 26 | Design MCP health check hangs from Python | #14 | fixed |
| 27 | Figma URL format /design/ vs /make/ | #14 | fixed |
| 28 | Subprocess timeouts too aggressive (300s) | #14 | fixed |
| 29 | Post-merge deps install uses HEAD~1 diff | #14 | fixed (e2e-reliability-fixes) |
| 30 | spec_coverage=fail causes unnecessary retry | #14 | open |
| 31 | Uncommitted work guard false positive on framework files | #15 | fixed |
| 32 | Agent wastes iterations on nonexistent openspec CLI | #15 | open |
| 33 | node_modules not installed in worktree (=Bug #29) | #15 | fixed (e2e-reliability-fixes) |
| 34 | Sentinel worktree removal crashes live Ralph | #15 | open |
| 35 | Ralph terminal PID reuse / log contamination | #15 | open |
| 36 | Uncommitted work guard retries with full redispatch | #15 | open |
| 37 | Verify retry exhaustion on build-fix iterations | #16 | fixed (`606aec640`) |
| 38 | Generated file conflicts block merge (.claude/* runtime files) | #16 | fixed (`eec894bcb`) |
| 39 | Dead agent not detected (ralph_pid=0 + no loop-state) | #16 | fixed |
| 40 | Monitor crash on state file race during manual edit | #16 | noise |
| 41 | Stale flock blocks sentinel restart (zombie PIDs) | #16 | fixed (e2e-reliability-fixes) |
| 42 | node_modules/ dirty files exhaust verify retries (Bug #37 root cause) | #17 | fixed (`606aec640`) |
| 43 | Dispatch races archive — new worktrees miss archive commits (Bug #38 partial fix) | #17 | partial (`d3604fef1`, `62c11ed71`) |
| 44 | pyyaml not installed for python3.14 — sentinel restart fails | #17 | fixed (manual pip install) |
| 45 | archive specs not committed to worktrees | #18 | fixed (`607d134ff`) |
| 46 | spec_verify timeout triggers retries | #18 | fixed (`021aa0818`) |
| 47 | figma-raw tsconfig exclude missing | #18 | fixed (`ff3997f`, set-project-web) |
| 48 | stale .next cache breaks build gate | #18 | fixed (`a68170397`) |
| 49 | decompose stderr swallowed by 2>/dev/null | #19 | fixed (`7551be1f5`) |
| 50 | state reconstruction loses merged status (no STATE_CHANGE events) | #19 | **open** |
| 51 | review template f-string crash (MAJOR — blocked all verify gates) | #19 | fixed (`957d125d9`) |
| 52 | orchestrator stuck during merge/archive — git_failed spam | #19 | fixed (`5c741058c`) |
| 53 | review diff truncation hides src/ files (false CRITICAL reviews) | #19 | fixed (`ab018fa88`) |
| 54 | engine.sh arithmetic crash from pipefail + grep no-match (context breakdown code) | #16* | fixed (`d8f2e7dad`) — sentinel self-healed |

## Token Efficiency Trend

| Run | Tokens/Change | Notes |
|-----|---------------|-------|
| #13 | 363k | Baseline with review gate |
| #14 | 338k | Partial (2 changes only) |
| #15 | 660k | Higher due to merge retries + Bug #34 waste |
| #16 | 418k | Best efficiency — improved verify gate, fewer wasted iterations |
| #17 | ~409k | 11 manual interventions all due to Bug #37 node_modules; fix deployed for #18 |
| #19 | ~456k | 2 manual merges (Bug #52); scope check retry waste ~100K/change |
| #16* | 55.5M | High token count due to 1M context window (Opus). Base context ~155K/iter, tools ~5.6M/iter |

## Recurring Issues

1. **pnpm-lock.yaml merge conflicts** — Runs #3, #8, #13, #14, #15. LLM merge resolver can't handle lockfiles. Needs regeneration strategy.
2. **node_modules missing in worktrees** — Runs #14, #15 (Bugs #29, #33). Worktrees don't get `node_modules/` after master merge.
3. **Package.json merge conflicts** — Runs #15. Manual deep-merge required for complex package.json changes.
