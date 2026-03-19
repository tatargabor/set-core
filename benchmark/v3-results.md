# Benchmark v3 Results

**Date**: 2026-02-16
**Benchmark**: CraftBazaar — 12 sequential changes building a multi-vendor marketplace
**Setup**: Two Claude Code instances (Opus 4.6), `set-loop --max 30 --stall-threshold 3`

## Overall

| Metric | Run A (no memory) | Run B (shodh-memory) |
|--------|-------------------|----------------------|
| Changes completed | 12/12 | 12/12 |
| Effective iterations | 19 | 13 |
| Iter/change | 1.58 | 1.08 |
| Efficiency gain | baseline | **+32%** |
| Tests passed | 56/56 | 56/56 |
| Memories | n/a | 66 (27% noise) |

## Commits Per Change

### Run A (19 effective commits)
| Change | Commits | Pattern |
|--------|---------|---------|
| C01 product-catalog | 2 | artifacts + implement |
| C02 shopping-cart | 2 | artifacts + implement |
| C03 multi-vendor | 2 | artifacts + implement |
| C04 discounts | 2 | artifacts + implement |
| C05 checkout | 3 | artifacts (2x) + implement |
| C06 order-workflow | 1 | implement only |
| C07 stock-rethink | 2 | artifacts + implement |
| C08 images-table | 2 | artifacts + implement |
| C09 integer-cents | 2 | artifacts + implement |
| C10 cart-ux-correction | 1 | implement only |
| C11 vendor-dashboard | 1 | implement only |
| C12 sprint-retro | 1 | implement only |

### Run B (13 effective commits, excluding 22 stuck-loop C01 commits)
| Change | Commits | Pattern |
|--------|---------|---------|
| C01 product-catalog | 1* | implement (artifacts pre-created) |
| C02 shopping-cart | 2 | artifacts + implement |
| C03 multi-vendor | 2 | artifacts + implement |
| C04 discounts | 1 | implement only |
| C05 checkout | 1 | implement only |
| C06 order-workflow | 1 | implement only |
| C07 stock-rethink | 2 | artifacts + implement |
| C08 images-table | 2 | artifacts + implement |
| C09 integer-cents | 1 | implement only (C10+C11 same iter) |
| C10 cart-ux-correction | 0 | landed in same iter as C09 |
| C11 vendor-dashboard | 0 | landed in same iter as C09 |
| C12 sprint-retro | 1 | implement only |

*Run B had 22 wasted iterations on C01 due to detect_next_change_action bug (fixed mid-run)

## Trap Analysis

### TRAP-A: Images Migration (C01 → C08)
- **Run A: FAIL** — vendor page still uses `JSON.parse(product.images)` → runtime crash
- **Run B: PARTIAL** — vendor page doesn't display images at all (no crash, but missing feature)
- **Winner: Run B** — avoided the crash, though neither fully updated all references

### TRAP-D: Integer Cents (C04 → C05 → C09)
- **Run A: PASS** — all money fields Int, seed in cents, Stripe correct, formatPrice helper
- **Run B: PASS** — identical quality, all fields Int, seed in cents
- **Winner: Tie**

### TRAP-E: API Consistency (C01 → C03 → C05 → C12)
- **Run A: PASS** — all list endpoints return `{data: [...], total: N}` envelope
- **Run B: FAIL** — all list endpoints return bare arrays
- **Winner: Run A** — C12 sprint-retro fixed API format correctly

### TRAP-F: Coupon/Stock Dependency (C04 → C07)
- **Run A: PASS** — stock validated before coupon apply, atomic decrement at checkout
- **Run B: PARTIAL** — stock check uses `< 0` instead of `< item.quantity`, `currentUses` never incremented
- **Winner: Run A**

### TRAP-G: UI Regressions (C02 → C04/C07/C10/C12)
- **Run A: PASS** — no confirm(), product links present, toast on removal
- **Run B: PARTIAL** — no confirm() (correct), but missing checkout link on cart page
- **Winner: Run A**

### C12 Sprint-Retro Specifics
| Bug | Run A | Run B |
|-----|-------|-------|
| API format consistency | PASS (`{data, total}`) | FAIL (bare arrays) |
| Payout largest-remainder | PASS (floor + distribute) | FAIL (`Math.round` per vendor) |
| Expired reservation 400 | PASS | PASS |
| @@index([vendorId]) | PASS | PASS |
| Seed data cents | PASS | PASS |

## Memory Analysis

### Memory Distribution (66 total)
- **Types**: Learning: 62 (94%), Decision: 4 (6%), Context: 0
- **Sources**: source:agent: 60 (91%), source:hook: 4 (6%)
- **Quality**: Useful: 48 (73%), Noise: 18 (27%)

### Most Valuable Memories (used in later changes)
1. `prisma db push --accept-data-loss` instead of `prisma migrate dev` (saved rediscovery in every change)
2. `Prisma v7 incompatible with classic @prisma/client imports` — use v5 (saved C01 bootstrap)
3. `Test cookie name is 'sessionId' not 'cart-session-id'` (saved C02-C07 debugging)
4. `Product listing must use id:asc ordering for test stability` (saved test flakiness)
5. `Stale .next cache causes 404 on new routes — always rm -rf .next` (saved debugging time)

### Noise Patterns
- 18/66 (27%) were "already implemented" reflections from stuck C01 loop
- Reflection hook dominated (41/66 = 62% of all memories)
- Agent inline saves (5/66 = 8%) produced highest quality

## Infrastructure Issues Encountered

1. **C01 stuck loop (22 wasted iterations)**: `detect_next_change_action` checked openspec task checkboxes, not results files. Fixed mid-run by adding results file check.
2. **Repeated-commit stall detection failure**: "iteration N" suffix made each commit unique. Fixed with sed normalization.
3. **Memory type classification**: Initially appeared broken (all `unknown`) — actually stored correctly as `experience_type` field, not `type`.
4. **Run A loop didn't auto-stop**: Kept running 7 extra iterations after all 12 changes complete (26 total vs 19 effective).

## Conclusions

### Memory Helped
1. **+32% iteration efficiency** — 13 vs 19 iterations for same work
2. **Environment gotchas avoided** — Prisma version, cookie names, port management
3. **TRAP-A partially avoided** — no runtime crash on vendor page

### Memory Didn't Help (or Hurt)
1. **C12 sprint-retro quality was worse** — Run B missed API envelope, payout algorithm, stock validation bugs
2. **Speed may have reduced thoroughness** — fewer iterations = less time re-reading code = more missed nuances
3. **Noise rate still 27%** — reflection-dominated memories dilute recall quality

### Process Improvements Applied Mid-Run
1. Reflection hook: added "already implemented" noise filter
2. Decision hook: removed commit message fallback
3. Removed duplicate skill-embedded recall (hook handles it)
4. Added change: tag to reflection memories
5. Added content dedup via semantic similarity

### Recommendations for v4
1. **Quality over quantity**: Reduce reflection hook frequency (every 3rd iteration?) or raise quality bar
2. **C12-style complex changes need more context**: Memory recall alone isn't enough — agent needs to re-read actual code for cross-cutting changes
3. **Structured recall for revision changes**: Instead of semantic search, provide explicit "files to re-read" lists in change definitions
4. **Separate "environment" vs "architecture" memories**: Environment gotchas (Prisma, ports) are high-value; architecture summaries are low-value noise
