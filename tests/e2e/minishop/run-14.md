# Run #14 (2026-03-15) — COMPLETED

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
