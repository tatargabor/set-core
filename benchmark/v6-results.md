# Benchmark v6 Results

**Date**: 2026-02-17
**Benchmark**: CraftBazaar — 12 sequential changes building a multi-vendor marketplace
**Setup**: Two Claude Code instances (Opus 4.6), `set-loop --max 30`
**v6 changes**: 3 new traps (L: responsive, M: pagination UI drift, N: toast drift), C12 expanded to 12 bugs, memory noise fixes (auto_ingest=False, change: tags, convention extraction), lib/ copy fix, ports 4000/4001

## Overall

| Metric | Run A (no memory) | Run B (shodh-memory) | Delta |
|--------|-------------------|----------------------|-------|
| Changes completed | 12/12 | 12/12 | tie |
| Productive iterations | 24 | 24 | tie |
| Idle tail iterations | 6 | 6 | tie |
| Time (wall clock) | ~2h (23:41→01:42) | ~2h20m (23:41→02:02) | A: -20min |
| Trap score (original A/B/D/E/F/G) | 4.5/6 | 4.5/6 | tie |
| Convention trap score (H/I/J/K/L) | 5/5 | 5/5 | tie |
| Drift trap score (M/N) | 2/2 | 1.5/2 | **A: +0.5** |
| Combined trap score | 11.5/13 | 11/13 | A: +0.5 |
| C12 bug score | 11/12 | 9/12 | **A: +2** |
| Memories | n/a | 57 | - |

## v5 → v6 Comparison

| Metric | v5 Run A | v5 Run B | v6 Run A | v6 Run B |
|--------|----------|----------|----------|----------|
| Changes completed | 12/12 | 12/12 | 12/12 | 12/12 |
| Productive iterations | 24 | 22 | 24 | 24 |
| Trap score (orig) | 4/5 | 3.5/5 | 4.5/6 | 4.5/6 |
| Convention traps | 3.5/4 | 4/4 | **5/5** | **5/5** |
| Drift traps | n/a | n/a | **2/2** | 1.5/2 |
| Combined traps | 7.5/9 | 7.5/9 | **11.5/13** | 11/13 |
| C12 bugs fixed | 9/9 | 8/9 | 11/12 | 9/12 |
| Memories | n/a | 83 | n/a | **57 (-31%)** |
| Memory noise | - | ~37% | - | **0%** |
| Code maps | - | 4/12 | - | 2/12 |
| Conventions saved | - | 0 | - | **6** |

### Key shift: Run A outperformed Run B on C12 and drift traps

Run A scored 11/12 on C12 bugs vs Run B's 9/12. Run B had issues with reservation expiry logic (Bug 3: false positives), responsive layout (Bug 10: homepage missing ResponsiveContainer), and Toast (Bug 12: per-page mount instead of global). Memory noise dropped to 0% (from 37%) but code map coverage regressed (4/12 → 2/12).

## Trap Analysis

### Original Traps

#### TRAP-A: Images Migration (C01 → C08)
- **Run A: PASS** — Image model properly normalized, no JSON.parse for images
- **Run B: PASS** — Same
- **Winner: Tie**

#### TRAP-B: $queryRaw Pain (C02 → C05)
- **Run A: PARTIAL** — 2 justified $queryRaw for atomic stock + 1 unnecessary $queryRawUnsafe for VendorPayout insert
- **Run B: PASS** — $queryRaw only for justified atomic stock operations
- **Winner: Run B**

#### TRAP-D: Integer Cents (C04 → C09)
- **Run A: PASS** — All money fields Int, formatPrice divides by 100
- **Run B: PASS** — Same
- **Winner: Tie**

#### TRAP-E: Error Format Inconsistency (C01 → C03 → C05 → C12)
- **Run A: PARTIAL** — ~15 error responses across 6 route files missing `code` field
- **Run B: PARTIAL** — 3 error responses in variants route missing `code` field
- **Winner: Run B** (much fewer violations)

#### TRAP-F: Coupon/Stock Cross-Dependency (C04 → C07)
- **Run A: PASS** — currentUses incremented in checkout-confirm, inside $transaction
- **Run B: PASS** — Same, inside $transaction
- **Winner: Tie** (FIRST TIME both runs pass TRAP-F after 3 consecutive failures!)

#### TRAP-G: UI Regressions (checkout navigation)
- **Run A: FAIL** — No "Proceed to Checkout" button/link in cart page
- **Run B: FAIL** — Same
- **Winner: Tie** (systemic miss, 4th consecutive benchmark)

#### Original Trap Summary

| Trap | Run A | Run B |
|------|-------|-------|
| A: Images | PASS | PASS |
| B: $queryRaw | PARTIAL (1 unnecessary) | PASS |
| D: Integer cents | PASS | PASS |
| E: Error format | PARTIAL (~15 missing) | PARTIAL (3 missing) |
| F: Coupon increment | **PASS** | **PASS** |
| G: Checkout button | FAIL | FAIL |
| **Score** | **4.5/6** | **4.5/6** |

*Scoring: PASS=1.0, PARTIAL=0.5, FAIL=0. TRAP-B: Run A partial due to unnecessary $queryRawUnsafe; Run B only justified uses. TRAP-E: both partial but Run B significantly better (3 vs 15 violations).*

### Convention Traps

#### TRAP-H: formatPrice Convention (C01 → C12)
- **Run A: PASS** — formatPrice exists, sole .toFixed(2) usage
- **Run B: PASS** — Same
- **Winner: Tie**

#### TRAP-I: Pagination Convention (C01 → C12)
- **Run A: PASS** — All list endpoints return { data, total, page, limit }
- **Run B: PASS** — Same
- **Winner: Tie**

#### TRAP-J: Error Codes Convention (C02 → C12)
- **Run A: PARTIAL** — errors.ts exists with 27 constants, but many routes use hardcoded strings
- **Run B: PASS** — errors.ts with 28 constants, all routes import from it
- **Winner: Run B**

#### TRAP-K: Soft Delete Convention (C01 → C12)
- **Run A: PASS** — All product queries filter deletedAt: null
- **Run B: PASS** — Same
- **Winner: Tie**

#### TRAP-L: Responsive Convention (C01 → C12) — NEW in v6
- **Run A: PASS** — ResponsiveContainer on all pages, custom sm:480px, no xl/2xl
- **Run B: PASS** — Same
- **Winner: Tie**

#### Convention Trap Summary

| Trap | Run A | Run B |
|------|-------|-------|
| H: formatPrice | PASS | PASS |
| I: Pagination | PASS | PASS |
| J: Error codes | PARTIAL | **PASS** |
| K: Soft delete | PASS | PASS |
| L: Responsive | PASS | PASS |
| **Score** | **4.5/5** | **5/5** |

### Implementation Drift Traps — NEW in v6

#### TRAP-M: Pagination UI Drift (C01 → C03 → C11 → C12)
- **Run A: PASS** — Shared Pagination component used on all list pages, no ad-hoc markup
- **Run B: PARTIAL** — Shared Pagination component exists, used on 2 pages, but imported-but-unused on 2 others (products, vendor detail)
- **Winner: Run A**

#### TRAP-N: Toast/Notification Drift (C02 → C05 → C06 → C10 → C12)
- **Run A: PASS** — Global Toast in layout.tsx with showToast(), zero window.alert/confirm
- **Run B: PARTIAL** — Toast exists but NOT globally mounted in layout.tsx; per-page mount means some pages lack notifications
- **Winner: Run A**

#### Drift Trap Summary

| Trap | Run A | Run B |
|------|-------|-------|
| M: Pagination UI | PASS | PARTIAL (unused imports) |
| N: Toast/notifications | PASS | PARTIAL (not global) |
| **Score** | **2/2** | **1.5/2** |

**Surprising result**: The drift traps (M/N), designed to favor the memory run, actually favored Run A. Run B's Pagination component wasn't fully integrated on all pages, and its Toast wasn't globally mounted. The hypothesis was that code-map memories would help Run B know WHERE each page's implementation was — but Run A's C12 implementation was cleaner despite having to search.

## C12 Sprint Retro: 12-Bug Analysis

| Bug | Run A | Run B |
|-----|-------|-------|
| 1. API format consistency | PASS | PASS |
| 2. Payout largest-remainder | PASS | PASS |
| 3. Expired reservation 400 | **PASS** | PARTIAL (false positive logic) |
| 4. @@index vendorId | PASS | PASS |
| 5. Seed data cents | PASS | PASS |
| 6. formatPrice consistency | PASS | PASS |
| 7. Error codes consistency | PARTIAL (hardcoded strings) | **PASS** |
| 8. Soft delete query audit | PASS | PASS |
| 9. Pagination API | PASS | PASS |
| 10. Responsive layout | **PASS** | PARTIAL (homepage missing) |
| 11. Pagination UI | PASS | PASS |
| 12. Toast/notifications | **PASS** (global) | PARTIAL (per-page) |
| **Total** | **11/12** | **9/12** |

*Scoring: PASS=1, PARTIAL=0 (noted qualitatively but scored as failure).*

### Key Findings

1. **TRAP-F FINALLY FIXED (both runs!)**: After 3 consecutive benchmark failures (v3, v4, v5), the explicit requirement in C07 ("Coupon currentUses MUST be incremented inside the checkout-confirm transaction") worked. Both runs implemented it correctly inside a $transaction. The P2 fix from v5-result-bugfixes paid off.

2. **Run B's C12 was weaker**: Run B missed 3 bugs partially (reservation logic, responsive homepage, toast mounting). Run A only missed 1 partially (error code strings). This is the opposite of the v6 hypothesis — memory didn't help with C12 quality.

3. **Error codes (Bug 7)**: Run B's error code consistency was BETTER than Run A — all routes import from errors.ts vs Run A's hardcoded strings. This is the one area where memory's convention knowledge may have helped.

4. **Toast architecture (Bug 12)**: Run A chose a global mount pattern (Toast in layout.tsx), Run B chose per-page mounts. The global pattern is architecturally superior — every page automatically gets toast support.

## Memory Analysis

### Memory Distribution (57 total)

| Metric | Value | v5 comparison |
|--------|-------|---------------|
| Total memories | 57 | 83 (-31%) |
| By type: Learning | 52 (91%) | 50 (60%) |
| By type: Decision | 3 (5%) | 1 (1%) |
| By type: Context | 2 (4%) | 11 (13%) |
| By type: Conversation (noise) | **0 (0%)** | 21 (25%) |
| By source: agent | 35 (61%) | 50 (60%) |
| By source: hook | 22 (39%) | 12 (14%) |
| Code maps | 2/12 (17%) | 4/12 (33%) |
| Conventions saved | **6** | 0 |
| With change: tag | **57/57 (100%)** | 52/83 (63%) |
| Untagged | **0 (0%)** | 31 (37%) |

### v5 → v6 Memory Quality

| Metric | v5 | v6 | Improvement |
|--------|----|----|-------------|
| Total memories | 83 | 57 | -31% (good — less noise) |
| Noise rate | ~37% | **0%** | Eliminated |
| Conversation type | 21 (25%) | **0** | auto_ingest=False fix worked |
| Untagged | 31 (37%) | **0** | change: tag fix worked |
| Convention memories | 0 | **6** | Convention extraction worked |
| Code maps | 4/12 | 2/12 | Regressed |
| Hook saves | 14% | **39%** | Better hook coverage |

### Convention Memories Saved

1. "All models must include deletedAt field for soft-delete; queries must filter deletedAt IS NULL" (change:discounts)
2. "All list endpoints use { data, total, page, limit } format" (change:checkout)
3. "New error codes for multi-vendor: VENDOR_NOT_FOUND, ORDER_NOT_FOUND..." (change:multi-vendor)
4. "All Product variants must have non-null name, sku, stockQuantity; use atomic Prisma transactions" (change:product-catalog)
5. "When migrating from denormalized to normalized data models, API response shape should remain stable" (change:images-table)
6. "Discount errors must include details object with affected items" (change:discounts)

These conventions WERE saved but their impact on C12 was mixed: Run B got error codes right (Bug 7) but missed other things.

### Code Map Regression

Only 2/12 code maps (product-catalog and multi-vendor) vs 4/12 in v5. The hook safety net generated these, but the agent didn't save additional code maps inline. This is a regression from v5 despite the "MANDATORY" instruction.

## Conclusions

### What improved (v5 → v6)

1. **Memory noise eliminated**: 37% → 0%. auto_ingest=False killed Conversation noise completely. change: tag fix gives 100% tagged memories. This was the #1 P0 recommendation from v5 and it worked perfectly.

2. **Convention extraction works**: 6 convention memories saved (0 in v5). The LLM prompt addition successfully extracts cross-cutting conventions from transcripts.

3. **TRAP-F finally fixed (both runs)**: After 3 benchmark failures, the explicit C07 requirement works. Both runs increment currentUses in checkout-confirm inside a transaction.

4. **Hook coverage up**: 14% → 39% of memories from hooks. Better automated knowledge capture.

### What didn't improve

1. **No measurable memory advantage**: Run A outscored Run B on traps (11.5 vs 11) and C12 (11 vs 9). Memory didn't help — it may have slightly hurt.

2. **Drift traps favored Run A**: The new M/N traps, designed to test code-map recall value, both went to Run A. Run B's implementations were incomplete (unused Pagination imports, non-global Toast).

3. **Code map coverage regressed**: 4/12 → 2/12. The agent still doesn't reliably save code maps despite MANDATORY instruction.

4. **TRAP-G checkout button still missing**: 4th consecutive benchmark where neither run adds a "Proceed to Checkout" link. Systemic blind spot.

5. **Run B was slower**: ~2h20m vs ~2h. Memory overhead (recall + save operations) added ~20 minutes.

### What's surprising

1. **Run A beat Run B on drift traps**: The hypothesis was that code-map memories ("C01 /products has Prev/Next, C03 /vendors has page numbers") would give Run B an advantage in unifying divergent implementations. Instead, Run A's clean-slate C12 audit produced better architecture (global Toast, complete Pagination). Memory may have created overconfidence — Run B "knew" what existed but didn't verify completeness.

2. **Convention memories helped exactly once (Bug 7)**: Run B's 100% error code adoption (all routes import from errors.ts) vs Run A's partial adoption is the clearest memory win. The "error codes convention" memory likely influenced this.

3. **Fewer memories = cleaner signal**: 57 memories vs 83, with 0% noise vs 37%. The quality improvement is dramatic, but the quantity didn't compensate for missing code maps.

4. **TRAP-F fix via explicit spec worked perfectly**: Both runs nailed it. This proves that some "traps" are really just spec ambiguity — when the requirement is explicit, both runs handle it correctly regardless of memory.

## Top 5 Improvement Recommendations

### 1. Make code map generation unconditional in hook (P0)

**Gap**: 2/12 code maps in v6 (worse than v5's 4/12). Agent ignores MANDATORY instruction.
**Evidence**: Only product-catalog and multi-vendor have code maps; 10 changes have none.
**Suggested change**: Generate code map in the save hook unconditionally after every commit — don't rely on the agent. Use git diff + file content parsing for semantic map.
**Expected impact**: 12/12 code map coverage, better recall for drift traps.

### 2. Add global architecture pattern to Toast/Pagination in C12 spec (P1)

**Gap**: Run B's Toast was per-page instead of global, Pagination was incomplete.
**Evidence**: Bug 12 says "shared toast system" but doesn't specify global mount. Bug 11 says "shared Pagination" but doesn't verify all pages.
**Suggested change**: C12 spec should say "Toast component must be mounted once in layout.tsx" and "Pagination must be rendered (not just imported) on all list pages."
**Expected impact**: Both runs get the architecture right.

### 3. Fix TRAP-G checkout navigation permanently (P1)

**Gap**: 4th consecutive benchmark failure. Neither run adds "Proceed to Checkout" to cart.
**Evidence**: v3, v4, v5, v6 all fail. Cart page renders items and totals but no navigation.
**Suggested change**: Add explicit acceptance criterion to C02 (shopping-cart): "Cart page must include a 'Proceed to Checkout' button/link that navigates to /checkout." Add test check.
**Expected impact**: Forces both runs to include the navigation element.

### 4. Investigate memory-induced quality regression (P1)

**Gap**: Run B scored lower on C12 (9/12 vs 11/12) despite having memory. Memory may introduce shortcuts or overconfidence.
**Evidence**: Run B's reservation logic had false positives, homepage missed ResponsiveContainer, Toast wasn't global — all suggesting less thorough C12 audit.
**Suggested change**: Add a recall-then-verify pattern to the CLAUDE.md memory instructions: "After recalling past implementation details, ALWAYS grep to verify current state — memory may be outdated."
**Expected impact**: Memory recall as starting point, not final answer.

### 5. Add intermediate test checks for drift traps (P2)

**Gap**: Drift traps (M/N) can only be evaluated at C12. No intermediate signal.
**Evidence**: Can't measure pagination UI or notification pattern divergence during C01-C11.
**Suggested change**: Add lightweight checks to test-02, test-05, test-06 that record (but don't fail on) what feedback pattern was used. This creates evaluation data without affecting the benchmark.
**Expected impact**: Better understanding of when and how drift occurs.

## Post-Run Investigation

### Cross-Contamination Audit

**Verdict: No contamination detected, but one design flaw identified.**

#### CRITICAL design flaw: Shared memory database

Both runs resolve to the same shodh-memory storage path (`~/.local/share/set-core/memory/craftbazaar`) because both projects are named "craftbazaar". Run B wrote 57 memories during the benchmark while Run A was running concurrently.

**However, Run A had no mechanism to read them:**
- Run A `settings.json`: NO memory hooks (verified via diff)
- Run A `CLAUDE.md`: NO memory instructions (zero mentions of set-memory/recall/remember)
- Run A skills: NO memory hooks (clean versions without `<!-- set-memory hooks -->` blocks)
- No global `~/.claude/CLAUDE.md` that could inject memory instructions

Triple-layer isolation (`--no-memory` hooks + clean CLAUDE.md + clean skills) prevented contamination despite the shared storage.

**Fix for v7**: Use different project names (e.g., `craftbazaar-baseline` vs `craftbazaar-memory`) to ensure physically separate memory databases.

#### Other findings (all clean)

| Check | Result |
|-------|--------|
| npm cache | Shared (symmetric, both benefit equally) |
| .next build cache | Independent (separate dirs/inodes) |
| node_modules | Independent (Run B has 4 extra Stripe packages) |
| Git config | Identical, minimal |
| Port separation | Correct (4000 vs 4001) |
| Ralph-loop config | Identical except port |

### Speed Investigation

**Verdict: Speed is legitimate. Test suite is too weak.**

#### Why both runs had 0 test-fix cycles

1. **v5 also had 0 test-fix cycles** — the OpenSpec ff→apply workflow with Opus 4.6 is highly reliable
2. **No glob bug** — v5 was split into 2 phases by the `0*.md` glob bug; v6 runs straight through
3. **Same iteration count** — v5 Run A: 24 iters, v6 Run A: 24 iters

#### Test suite weaknesses (CRITICAL)

**test-12 passes 15/21 checks with NO running server** — 71% of checks are file/grep-based:

| Check Type | Count | Example |
|------------|-------|---------|
| File existence | 5 | `[ -f src/components/Pagination.tsx ]` |
| Grep/import check | 8 | `grep "Pagination" "$PAGE_FILE"` |
| Config check | 2 | `grep "480" tailwind.config.ts` |
| API/curl check | 6 | `curl -s "$BASE/api/products"` |

**Specific weaknesses:**

| Issue | Severity | Impact |
|-------|----------|--------|
| **Payout auto-pass**: `no_multi_vendor_orders` → `check ... 'true'` | P0 | Largest-remainder algorithm NEVER tested |
| **TRAP-M checks import, not render**: `grep "Pagination"` matches `import` statements | P0 | Run B passes despite products page not rendering `<Pagination>` |
| **TRAP-N no global check**: doesn't verify Toast in `layout.tsx` | P1 | Run B passes with per-page mounts (incomplete coverage) |
| **Vendor regression skips silently**: `if [ -n "$VENDOR_DASH_ID" ]` | P1 | 2 checks silently skipped in both runs |

#### Token analysis reveals memory DID help on C12

| Metric | Run A | Run B |
|--------|-------|-------|
| C12 sprint-retro tokens | **1,023K** | **502K** |
| C12 wall time | 14m53s | 17m45s |

Run B used **half the tokens** on C12 (502K vs 1,023K) despite taking slightly longer (memory hook overhead). This suggests memory recall DID reduce exploration — Run B needed less searching to find affected files. However, the reduced exploration led to sloppier implementation (false-positive reservation logic, incomplete Pagination render, non-global Toast).

**Interpretation**: Memory helps with efficiency (fewer tokens = less searching) but may reduce thoroughness. The baseline agent's exhaustive search produced more complete implementations.

### Recommended test fixes for v7

| Priority | Fix | Expected effect |
|----------|-----|-----------------|
| P0 | test-12 Bug 2: FAIL on `no_multi_vendor_orders` or create test order | Forces payout algorithm verification |
| P0 | test-12 TRAP-M: `grep "<Pagination"` instead of `grep "Pagination"` | Run B would FAIL (import-only on products) |
| P1 | test-12 TRAP-N: Add check for `Toast` in `layout.tsx` | Run B would FAIL (no global mount) |
| P1 | test-12 vendor regression: FAIL instead of skip when no vendor ID | 2 more checks would execute |
| P2 | Rebalance test-12: add more curl/behavioral checks | Reduce no-server pass rate from 71% to <30% |
