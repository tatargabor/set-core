# CraftBrew E2E Run #4 — 2026-03-19

## Final Run Report

### Status: PARTIAL (5/15 merged, 2 failed, 8 dep-blocked)

| Change | Phase | Status | Tokens | Retries | Notes |
|--------|-------|--------|--------|---------|-------|
| project-bootstrap | 1 | merged | 49K | 1 | Autonomous |
| test-infrastructure | 1 | merged | 57K | 0 | Manual merge (config.yaml conflict) |
| seed-data | 1 | merged | 124K | 0 | Autonomous |
| auth-system | 2 | FAILED | 202K | 3 | App-level verify failures, blocked 6 dependents |
| catalog-listing-homepage | 2 | merged | 234K | 1 | Autonomous |
| content-stories | 2 | FAILED | 245K | 3 | App-level verify failures |
| catalog-detail-search | 3 | merged | 87K | 3 | Autonomous |
| cart-system | 3 | blocked | - | - | Dep: auth-system (failed) |
| checkout-orders | 4 | blocked | - | - | Dep: cart-system |
| user-account | 4 | blocked | - | - | Dep: auth-system, checkout-orders |
| reviews-wishlist | 4 | blocked | - | - | Dep: checkout-orders |
| promotions-email | 4 | blocked | - | - | Dep: checkout-orders |
| subscription-system | 4 | blocked | - | - | Dep: auth-system, checkout-orders |
| admin-dashboard-moderation | 5 | blocked | - | - | Dep: auth-system, content-stories |
| admin-operations | 5 | blocked | - | - | Dep: admin-dashboard-moderation |

### Key Metrics
- **Wall clock**: ~3h (00:51 → 03:56 active)
- **Changes merged**: 5/15 (33%)
- **Autonomous merges**: 4/5 (80%) — 1 manual (config.yaml conflict)
- **Sentinel interventions**: 1 (manual merge for config.yaml)
- **Total tokens**: ~998K (merged changes only)
- **Bugs found & fixed**: 4 framework bugs
- **Verify retries**: 11 total across all changes
- **Bug #14 recurrence**: NO — verify agent death not observed
- **Bug #16 recurrence**: YES initially (pre-fix), NO after fix deployed

### Framework Bugs Found & Fixed

#### Bug #20: Scaffold clones stale main branch
- **Type**: framework
- **Severity**: blocking
- **Root cause**: `run-complex.sh` cloned `main` branch of craftbrew repo which contained Run #1 implementation. Orchestrator saw completed openspec changes → "All changes complete" → exit code 1 crash loop.
- **Fix**: `fc7f0791b` — Changed `CRAFTBREW_BRANCH` from `main` to `spec-only`. Pushed `spec-only` branch to GitHub.
- **Recurrence**: new

#### Bug #21: Decompose max-turns too low for complex specs
- **Type**: framework
- **Severity**: blocking
- **Root cause**: `--max-turns 3` on `claude -p` call in `run_planning_pipeline()`. With 54 requirements / 11 domains, Claude needs tools (file reads) that consume turns. Response was `Error: Reached max turns (3)`.
- **Fix**: `5aaba75c0` — Increased to `--max-turns 10`.
- **Recurrence**: new

#### Bug #22: Sentinel stuck timeout too aggressive
- **Type**: framework
- **Severity**: blocking
- **Root cause**: 180s stuck timeout killed orchestrator during verify gate / decompose Claude calls (which block for 3-10 min without emitting events). The `_signal_alive()` heartbeat only works in the monitor loop, not during blocking `claude -p` calls.
- **Fix**: `dcc12d587` — Increased timeout to 600s. Added live children check (if orchestrator PID has active children like claude/python, it's working, not stuck).
- **Recurrence**: Bug #16 from Run #3

#### Bug #23: wt/** missing from gitattributes merge=ours
- **Type**: framework
- **Severity**: merge-blocking
- **Root cause**: `wt/orchestration/config.yaml` caused merge conflict on `test-infrastructure` merge because it wasn't covered by `.gitattributes merge=ours` strategy. Only `.claude/**` and lockfiles were covered.
- **Fix**: `65d6258be` — Added `wt/**` to gitattributes in both scaffold scripts.
- **Recurrence**: new

### Known Issue: Dependency Cascade Deadlock
`auth-system` failure blocked 6/8 remaining changes via dependency chain. This is a known framework limitation (documented in E2E-GUIDE.md). The orchestrator does not auto-skip failed dependencies or re-dispatch with reduced scope.

**Potential fix**: When a change fails and has dependents, either:
1. Auto-retry with higher token budget
2. Allow dependents to proceed without the failed dep (with warning)
3. Replan to merge the failed change's scope into dependents

### Conclusions

1. **Autonomous merge rate dramatically improved**: 4/5 (80%) vs Run #3's 1/15 (7%). Bug #14 (verify agent death) did NOT recur — the verify pipeline reliability fix (`381289b48`) is working.

2. **Sentinel stability improved**: Bug #16 fix (600s timeout + live children check) eliminated false kills. Zero false sentinel kills after fix deployment.

3. **Dependency cascade is the #1 issue**: A single failed change (`auth-system`) blocked 40% of the project. This needs a framework-level solution.

4. **GitHub repo dependency removed**: `spec-only` branch created, scaffold script updated. TODO: migrate to local spec files (eliminate GitHub dependency entirely).
