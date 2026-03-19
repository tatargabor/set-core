# MiniShop E2E Run #18 (2026-03-17)

## Status: INTERRUPTED (1/10 merged, 2 failed, 7 pending)

Multiple mid-run fix/restart cycles. Primary goal was validating Bug #45 (specs commit) and discovering new framework bugs.

| Change | Status | Tokens | Retries | Build | Notes |
|--------|--------|--------|---------|-------|-------|
| project-init | **merged** | 393K | 0 | - | Clean, 0 interventions |
| storefront-catalog | **merged** (earlier) / failed (retry) | 407K+344K | 2+2 | pass | First merge validated Bug #45 |
| auth-system | failed | 381K+708K+0 | 2+2+0 | pass/fail | bcryptjs Edge Runtime, stale state |
| product-detail | failed | 464K+1018K | 0+2 | pass | scope_check fail |
| 6 others | pending | 0 | - | - | Never dispatched (Phase 2 blocked) |

## Bugs Found & Fixed

### Bug #45: archive_change() doesn't commit specs/ (CRITICAL)
- **Type**: framework / blocking
- **Root cause**: `openspec archive --yes` CLI writes specs to `openspec/specs/` and moves change to archive/, but does NOT run `git add/commit`. The merger.py `archive_change()` didn't commit either. New worktrees never saw specs.
- **Fix**: `607d134ff` — `git add openspec/ && git commit` after archive CLI
- **Verified**: YES — storefront-catalog specs (navigation-header, product-catalog) auto-committed on merge

### Bug #46: spec_verify timeout triggers expensive retries (CRITICAL)
- **Type**: framework / blocking
- **Root cause**: `/opsx:verify` via `run_claude --max-turns 20` rarely produces `VERIFY_RESULT: PASS/FAIL` sentinel. Missing sentinel → `verify_ok = False` → retry. Each change burned 2 retries (~400K tokens each) for nothing.
- **Fix 1**: `a3ee2ca78` — increased max-turns 20→40 (insufficient alone)
- **Fix 2**: `021aa0818` — timeout is non-blocking (does NOT set `verify_ok = False`)
- **Verified**: Partial — non-blocking fix prevents timeout from causing retry, but 40 turns still not enough for VERIFY_RESULT

### Bug #47: Figma raw source files break Next.js build
- **Type**: framework / blocking
- **Root cause**: `docs/figma-raw/.../src__app__App.tsx` imports `react-router` which isn't in deps. tsconfig.json `include: ["**/*.ts", "**/*.tsx"]` picks up these design reference files.
- **Fix**: `ff3997f` (set-project-web) — `"exclude": ["node_modules", "docs/figma-raw"]` in tsconfig template
- **Verified**: YES — auth-system build=pass after fix

### Bug #48: Stale .next cache causes ENOENT build failures
- **Type**: framework / blocking
- **Root cause**: `.next/server/pages-manifest.json` and `.next/export/500.html` ENOENT after previous build iterations. Agent's build_fix_attempts can't resolve filesystem-level cache corruption.
- **Fix**: `a68170397` — `shutil.rmtree(.next)` before build gate
- **Verified**: YES (indirectly — subsequent builds pass)

### Edge Runtime: bcryptjs auth rule (set-project-web)
- **Fix**: `ca67130` — auth-conventions.md warns about Edge Runtime incompatibility
- **Verified**: Untested — auth-system didn't reach full validation

## Key Metrics
- **Wall clock**: ~3h (with multiple restarts)
- **Changes merged**: 1/10 (project-init) + 1 storefront-catalog (earlier cycle)
- **Sentinel interventions**: 6+ (all manual fix/deploy/restart)
- **Total tokens**: ~5M+ (across all restart cycles)
- **Bugs found & fixed**: 4 framework + 1 template
- **Verify retries wasted by Bug #46**: ~8 (2 per change × 4 changes)

## Conclusions

1. **Bug #45 (specs commit) was the most important fix** — validates that the openspec pipeline actually propagates knowledge between phases
2. **Bug #46 (spec_verify timeout) was the most expensive bug** — each change wasted 2 retries × ~200K tokens = ~400K per change, ~1.6M total
3. **Multiple mid-run restarts corrupt state** — partial resets don't clear all fields (merge_retry_count, gate_retry_*), causing instant-fail on redispatch. Need a more robust reset function.
4. **Run #19 should be a clean `run.sh`** — no mid-run restarts, all 6 fixes deployed from start
5. **scope_check gate** needs investigation — storefront-catalog failed on scope_check even with build/test/review all passing
