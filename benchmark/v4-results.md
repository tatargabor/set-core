# Benchmark v4 Results

**Date**: 2026-02-16
**Benchmark**: CraftBazaar — 12 sequential changes building a multi-vendor marketplace
**Setup**: Two Claude Code instances (Opus 4.6), `set-loop --max 30 --stall-threshold 3`

## Overall

| Metric | Run A (no memory) | Run B (shodh-memory) |
|--------|-------------------|----------------------|
| Changes completed | 12/12 | 12/12 |
| Effective commits | 23 | 23 |
| Commit pattern | strict 2/change (artifacts + implement) | strict 2/change (artifacts + implement) |
| Trap score | 3.5/5 | 3.5/5 |
| Tests passed | all | all |
| Memories | n/a | 51 |

## v3 → v4 Comparison

| Metric | v3 Run A | v3 Run B | v4 Run A | v4 Run B |
|--------|----------|----------|----------|----------|
| Effective iterations | 19 | 13 | ~23 | ~23 |
| Iter/change | 1.58 | 1.08 | ~1.9 | ~1.9 |
| Trap score | **4.0/5** | **1.5/5** | **3.5/5** | **3.5/5** |
| Memories | n/a | 66 (27% noise) | n/a | 51 (~15% noise) |

### Key shift: v3 memory = faster but sloppier, v4 memory = same speed, same quality

In v3, memory gave +32% iteration efficiency but caused 2.5-point quality drop on traps. In v4, the efficiency gap disappeared but so did the quality gap — memory no longer hurts code quality. The memory run's absolute trap score jumped from 1.5/5 to 3.5/5.

## Trap Analysis

### TRAP-A: Images Migration (C01 → C08)
- **Run A: PASS** — all pages use Image relation, no JSON.parse on images
- **Run B: PASS** — same, all pages correctly migrated
- **Winner: Tie** (both improved over v3)

### TRAP-D: Integer Cents (C04 → C05 → C09)
- **Run A: PARTIAL** — schema/seed/formatPrice all correct, but vendor page and checkout page use `.toFixed(2)` directly on cents instead of `formatPrice()`
- **Run B: PASS** — all money fields Int, seed in cents, formatPrice used consistently
- **Winner: Run B**

### TRAP-E: API Consistency (C01 → C03 → C05 → C12)
- **Run A: PASS** — all list endpoints return `{data, total}` envelope
- **Run B: PASS** — same, all endpoints compliant
- **Winner: Tie** (Run B fixed its v3 FAIL)

### TRAP-F: Coupon/Stock Dependency (C04 → C07)
- **Run A: PARTIAL** — stock at checkout: PASS, `< item.quantity` validation: PASS, coupon `currentUses` increment: FAIL
- **Run B: PARTIAL** — identical pattern: stock at checkout works, but `currentUses` never incremented
- **Winner: Tie** (both miss coupon tracking)

### TRAP-G: UI Regressions (C02 → C04/C07/C10/C12)
- **Run A: PARTIAL** — no confirm(), has /products link, but missing checkout link/button
- **Run B: PARTIAL** — identical: no confirm(), has /products link, missing checkout link
- **Winner: Tie** (both miss checkout navigation)

### C12 Sprint-Retro Specifics

| Bug | v3 Run A | v3 Run B | v4 Run A | v4 Run B |
|-----|----------|----------|----------|----------|
| API format consistency | PASS | FAIL | **PASS** | **PASS** |
| Payout largest-remainder | PASS | FAIL | **FAIL** | **PARTIAL** |
| Expired reservation 400 | PASS | PASS | **PASS** | **FAIL** |
| @@index([vendorId]) | PASS | PASS | **PASS** | **PASS** |
| Seed data cents | PASS | PASS | **PASS** | **PASS** |

## Memory Analysis

### Memory Distribution (51 total)
- **Types**: Learning: ~35, Decision: ~6, Context: ~10
- **Sources**:
  - source:agent (reflection hook): ~18 (35%)
  - source:agent (inline saves): ~18 (35%)
  - source:hook (transcript LLM extraction): ~6 (12%)
  - source:hook (decision extraction): ~2 (4%)
  - Other: ~7 (14%)
- **Noise estimate**: ~15% (down from v3's 27%)

### v3 → v4 Memory Quality Improvements

| Metric | v3 | v4 |
|--------|----|----|
| Total memories | 66 | 51 |
| Noise rate | 27% | ~15% |
| Reflection hook share | 62% | 35% |
| Agent inline share | 8% | **35%** |
| Transcript hook share | 0% | **12%** |
| Decision hook share | 6% | 4% |

The biggest improvement: agent inline saves jumped from 8% to 35%. The transcript-based haiku extraction added a new 12% source that works regardless of agent compliance.

### Most Valuable Memory Types
1. **Environment gotchas** (Prisma v7, Tailwind v4, port conflicts) — saved rediscovery across changes
2. **Test expectations** (cookie names, ordering, SSR requirements) — prevented debugging loops
3. **Schema migration patterns** (force-reset, default values) — reused in C07-C09

## Changes from v3

### Hook improvements applied before v4
1. **Reflection hook**: added `change:` tag, content dedup via semantic similarity, "already implemented" noise filter
2. **Decision hook**: only saves when real `**Choice**:` lines found, no commit message fallback
3. **Skill recall**: removed from 5 skills (hook handles it), kept in explore skill
4. **Recall hook**: added REREAD_FILES mandatory file-reading lists for C07-C12
5. **NEW: Transcript extraction**: haiku LLM auto-extracts insights from session transcripts on Stop hook

### REREAD_FILES injection (the key v4 improvement)
For changes C07-C12 (revision/correction/retro), the recall hook now injects explicit file lists that the agent MUST read before implementing. Example for sprint-retro:
```
CRITICAL: This change fixes 5 cross-cutting bugs. You MUST re-read actual code, not rely on memory.
RE-READ these files BEFORE implementing ANY fix:
  Bug 1 (API format): src/app/api/products/route.ts, src/app/api/vendors/route.ts, ...
  Bug 2 (Payout rounding): src/app/api/checkout/ — find where payout split happens
  ...
```

This directly addressed v3's "overconfidence problem" — where memory gave agents surface facts but not deep structural understanding.

## Infrastructure Notes

1. **Auto-stop bug persists**: Both loops ran to max 30 iterations despite finishing all 12 changes. Same issue as v3 Run A.
2. **Transcript extraction hook**: worked correctly, produced 6 memories from auto-extraction. The async background fork was implemented mid-run (won't affect v4 results but improves v5 latency).
3. **No C01 stuck loop**: v3's detect_next_change_action bug was already fixed.

## Conclusions

### What improved
1. **Memory no longer hurts code quality**: v3 Run B scored 1.5/5, v4 Run B scored 3.5/5 (+133%)
2. **TRAP-A fully fixed**: both runs pass images migration (v3 both failed/partial)
3. **TRAP-E fixed for memory run**: API consistency now passes (was v3's worst failure)
4. **Memory noise reduced**: 27% → ~15%, better signal-to-noise ratio
5. **Agent compliance improved**: inline saves 8% → 35%

### What didn't improve
1. **No efficiency advantage**: v4 iter/change ~1.9 for both runs (v3 had +32% for memory)
2. **TRAP-F still fails for both**: coupon `currentUses` never incremented — neither run catches this
3. **TRAP-G checkout link missing for both**: systemic issue, not memory-related
4. **Payout algorithm**: neither run implements largest-remainder correctly

### Remaining gaps (for v5)
1. **Coupon tracking & checkout navigation** are missed by BOTH runs — these are spec comprehension issues, not memory issues. May need spec-level hints or more explicit change definitions.
2. **Payout algorithm** is consistently wrong — the "largest-remainder" concept may need a concrete code example in the change definition, not just a name.
3. **Memory should beat baseline, not just match**: the REREAD_FILES approach equalized quality but didn't create an advantage. Next step: save architectural "code maps" (which functions live where, what depends on what) that give the memory run structural understanding the baseline lacks.
4. **Auto-stop bug**: loop should detect all results files exist and stop. Fix the done-detection in set-loop.
