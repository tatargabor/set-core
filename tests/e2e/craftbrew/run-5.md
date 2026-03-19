# CraftBrew Run #5 — 2026-03-19/20

## Setup
- **set-core commit**: `80b72d5b8` (fix: prevent origin remote contamination)
- **Project dir**: `/home/tg/.local/share/set-core/e2e-runs/craftbrew-run5`
- **Config**: max_parallel=2, checkpoint_every=3, default_model=opus, smoke=pnpm build && pnpm test
- **Spec**: 24 files in docs/, 45 requirements, 9 domains → 15 changes planned

## Timeline
- 22:37 — Sentinel started, digest generated (45 reqs, 9 domains)
- 22:47 — Plan created (15 changes), Phase 1 dispatch: `project-infrastructure`
- 23:01 — `project-infrastructure` iter 1 done (37K tokens, 13 min)
- 23:06 — `project-infrastructure` **MERGED** (0 retries)
- 23:08 — Phase 1 continues: `database-schema` dispatched
- 23:22 — `database-schema` iter 1 done (45K tokens, 14 min)
- 23:27 — `database-schema` verify+merge — **Bug #24 triggered** (origin remote contamination)
- 23:27–23:40 — **Blocker**: `build_broken_on_main` — 31 files with conflict markers from upstream repo
- 23:40 — Fix deployed: reset main, cherry-pick clean commits, remove origin, prisma generate, restart
- 23:40 — `auth-and-accounts` dispatched (Phase 2)
- 00:00 — `auth-and-accounts` iter 1 done (68K tokens)
- 00:07 — Verify retry: IDOR, open redirect, JWT secret fixes
- 00:15 — Verify retry #2: React 18 compatibility fix
- 00:23 — `auth-and-accounts` **FAILED** — context overflow (443K/200K), retries exhausted
- 00:26 — All 12 remaining changes BLOCKED (dependency cascade deadlock)
- 00:28 — Sentinel stopped, wrap-up started

## Results

### Status: PARTIAL (2/15 merged, 1 failed, 12 blocked)

| Change | Status | Tokens | Time | Notes |
|--------|--------|--------|------|-------|
| project-infrastructure | merged | 37,594 | ~13m | Clean scaffold, 0 retries |
| database-schema | merged | 47,395 | ~15m | 17 models + seed, 0 retries. Bug #24 on merge. |
| auth-and-accounts | FAILED | 92,636 | ~43m | Context overflow 443K/200K. 3 verify retries. |
| shared-layout | blocked | — | — | depends_on: auth-and-accounts |
| product-catalog-list | blocked | — | — | depends_on: shared-layout |
| product-detail-search | blocked | — | — | depends_on: product-catalog-list |
| promotions-and-emails | blocked | — | — | depends_on: auth-and-accounts |
| content-stories | blocked | — | — | depends_on: shared-layout |
| cart-and-shipping | blocked | — | — | depends_on: product-detail-search, promotions |
| checkout-and-orders | blocked | — | — | depends_on: cart-and-shipping |
| reviews-wishlist | blocked | — | — | depends_on: product-detail-search, auth |
| homepage | blocked | — | — | depends_on: 4 changes |
| subscription-system | blocked | — | — | depends_on: checkout-and-orders |
| admin-dashboard-products-orders | blocked | — | — | depends_on: checkout, subscription |
| admin-promotions-content-moderation | blocked | — | — | depends_on: admin-dashboard, reviews, stories |

### Key Metrics
- **Wall clock**: ~1h 51m (22:37–00:28)
- **Changes merged**: 2/15 (13%)
- **Sentinel interventions**: 1 (Bug #24 fix)
- **Total tokens**: ~177K
- **Bugs found & fixed**: 2 (Bug #24 fixed mid-run, Bug #25 observed)
- **Verify retries**: 3 (all on auth-and-accounts)
- **Monitor auto-resumes**: 5 (sentinel watchdog too aggressive)

## Bugs

### 24. Origin remote contamination in merge pipeline
- **Type**: framework
- **Severity**: blocking
- **Root cause**: `run-complex.sh` clones from GitHub repo but doesn't remove `origin` remote. The merger.py agent rebase prompt instructs agents to `git fetch origin main && git merge origin/main`, which pulls the full upstream implementation into the local spec-only branch. This caused 31 files with conflict markers on main after database-schema merge.
- **Fix**: `80b72d5b8` — (1) scaffold removes origin after clone, (2) merger uses `git merge main` (local ref only)
- **Deployed mid-run**: yes, unblocked orchestration
- **Recurrence**: new

### 25. Sentinel watchdog kills monitor too aggressively
- **Type**: framework
- **Severity**: noise (non-blocking due to auto-resume)
- **Root cause**: Monitor process was killed and restarted 5 times during the run (~every 10 minutes). The sentinel watchdog 600s timeout triggers even when the monitor is healthy but idle (waiting for agent to finish). Each restart costs token overhead for state re-parsing.
- **Fix**: open — need to check if monitor emits heartbeats during idle wait periods
- **Recurrence**: possible regression of Bug #16 fix (dcc12d587)

### 26. Dependency cascade deadlock (recurrence)
- **Type**: framework (known limitation)
- **Severity**: blocking
- **Root cause**: When `auth-and-accounts` failed, all 12 dependent changes stayed `pending` forever. The orchestrator doesn't auto-skip or replan around failed dependencies. Same pattern as Run #4 (auth-system failure blocked 6/8 changes).
- **Fix**: open — documented in E2E-GUIDE.md "Known Framework Limitations". Needs auto-propagation: if a dep fails, dependents should be marked `skipped` or trigger a replan.
- **Recurrence**: Run #4, Run #5

### 27. Auth change context overflow (443K/200K)
- **Type**: app-level (but decompose could prevent)
- **Severity**: blocking
- **Root cause**: auth-and-accounts scope too large for single agent context (registration, login, session, middleware, account pages, legal pages, IDOR protection — all in one change). Agent hit 443K tokens, 222% of 200K window. Verify retries compounded the overflow.
- **Fix**: open — decompose should split M-sized auth changes into smaller pieces, or use opus-1m model for large changes
- **Recurrence**: similar to Run #2 Bug #10 (database-schema 970K overflow)

## Conclusions

1. **Origin remote contamination (Bug #24)** was the only real framework bug this run. Fixed mid-run with a 2-line change. The scaffold and merger now handle local-only repos correctly.

2. **First 2 changes were flawless**: project-infrastructure (13m, 37K) and database-schema (15m, 45K) both merged on first try with 0 retries. The pipeline is reliable for S-M sized infrastructure/schema changes.

3. **Auth change too large for 200K context**: The decompose step should either (a) split auth into 2-3 smaller changes (registration, session/middleware, account pages) or (b) route M+ auth changes to opus-1m model. This is the same class of problem as Run #2 Bug #10.

4. **Dependency cascade still unhandled**: For the 3rd consecutive run (Run #3, #4, #5), a single failure in the dependency chain blocks all downstream work. This is the #1 priority framework improvement — auto-skip or replan when a dependency fails.

5. **Monitor instability (5 restarts)**: Not blocking but wasteful. The sentinel watchdog may need a longer grace period when agents are actively running (check for live children before killing).

### Priority fixes for Run #6
1. **Dependency cascade handling** — auto-skip or replan around failed deps (Bug #26, recurrent)
2. **Large change splitting** — decompose should cap auth/feature changes at ~30K token budget
3. **Monitor heartbeat during idle** — prevent unnecessary watchdog kills (Bug #25)
