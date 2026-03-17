# CraftBrew Run #2 — 2026-03-17

**Project dir**: `/tmp/craftbrew-run2`
**wt-tools commit**: `ea54fe779` (post-run17 fixes)
**Spec**: `docs/` (multi-file directory spec)
**Config**: max_parallel=2, checkpoint_every=3, smoke=`pnpm build && pnpm test`

## Prep Context (from Run #1)

- **Run #1 baseline**: 15/15 merged | 9h | 11M tokens | 7 interventions
- **Bug #37 fix now active** (node_modules dirty → verify exhaustion) — expect fewer retries
- **pyyaml fix** deployed to python3.14
- **Watch for**: Bug #43 (dispatch races archive for openspec dirs)

## Bugs Found This Run

### 1. Bug #37 fix not yet effective — orchestrator cache
- **Type**: framework / deployment issue
- **Severity**: blocking (same as minishop run #17)
- **Root cause**: `git_utils.py` `606aec640` fix (node_modules kizárás) nem érte el az orchestrator processzt, mert az orchestrator induláskor cache-eli a Python modulokat. A fix csak a következő fresh orchestrator-indításnál lép életbe.
- **Evidence**: `i18n-routing-foundation` ret=2 → failed (verify retry exhaustion), pontosan mint minishop-ban
- **Status**: Minishop Run #18-tól fog hatni (ott már friss orchestrator indul)

### 2. State file lost during manual merge cleanup
- **Type**: framework
- **Severity**: blocking
- **Root cause**: `wt-merge i18n-routing-foundation` cleanup step törölte/nem találta az `orchestration-state.json` fájlt. A craftbrew projekt state fájl ugyanoda kerül mint a minishop, de valami miatt a merge cleanup eltávolította.
- **Status**: Identified. Recovery nem volt lehetséges, run megszakítva.

### 3. Context overflow — database-schema 970K (485% of 200K window)
- **Type**: app bug (agent túl sokat dolgozik egy iterációban)
- **Severity**: blocking (spec verify timeout)
- **Root cause**: A database-schema change nagyon komplex (Prisma schema, migrations, seeds), az agent 970K tokent használt egyetlen iterációban
- **Status**: App bug, nem framework. Szükséges lehet a change felosztása.

### 4. Spec verify timeout — both changes
- **Type**: noise/known limitation
- **Root cause**: `VERIFY_RESULT sentinel in output` timeout — a verify review agent API hívása 306K+ context-tel időtúllépett
- **Status**: Ismert, nem új bug

## Phase Log

| Time | Event |
|------|-------|
| 05:25 | Scaffold complete → `/tmp/craftbrew-run2` |
| 05:25 | Sentinel started, digest running (multi-file spec) |
| 05:47 | Planning complete, `test-infrastructure-setup` dispatched |
| ~06:07 | `test-infrastructure-setup` MERGED ✓ |
| ~06:07 | `database-schema` + `i18n-routing-foundation` dispatched |
| ~06:35 | `i18n-routing-foundation` failed (ret=2) → manuálisan merged |
| ~06:35 | State fájl elveszett a merge cleanup-ban |
| ~06:36 | **Run leállítva** |

## Final Run Report

### Status: INTERRUPTED (2/15 merged — 1 auto + 1 manual)

| Change | Status | Tokens | Notes |
|--------|--------|--------|-------|
| test-infrastructure-setup | merged ✓ | ~100K | Auto-merged by orchestrator |
| i18n-routing-foundation | merged ✓ | 568K | Manual (ret=2 verify exhaustion) |
| database-schema | interrupted | 970K | Context overflow (485%), build fail |
| többi 12 | never dispatched | — | Run interrupted |

### Key Metrics
- **Wall clock**: ~1h10m (05:25 → 06:36)
- **Changes merged**: 2/15
- **Sentinel interventions**: 1 manual merge
- **Bugs found**: 4 (cached fix, state lost, context overflow, verify timeout)

### Conclusions
1. **Bug #37 fix (node_modules)** hatékony lesz Run #18-tól — az orchestrator cache-eli a modult, ezért ez a run még a régi kóddal futott
2. **State fájl elvesztése** új bug — a `wt-merge` cleanup valami okból törölte. Vizsgálni kell.
3. **Context overflow** (970K) craftbrew-specifikus app bug — a database-schema change túl komplex, felosztás szükséges lehet
4. **Craftbrew Run #3** előtt: state-fájl törlés bugot javítani kell
