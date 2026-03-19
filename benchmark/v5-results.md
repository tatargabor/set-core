# Benchmark v5 Results

**Date**: 2026-02-16
**Benchmark**: CraftBazaar — 12 sequential changes building a multi-vendor marketplace
**Setup**: Two Claude Code instances (Opus 4.6), `set-loop --max 30` (Phase 1) + `--max 15` (Phase 2)
**v5 changes**: 4 new convention traps (H/I/J/K), code map memories, glob bug fix for changes 10-12

## Overall

| Metric | Run A (no memory) | Run B (shodh-memory) | Delta |
|--------|-------------------|----------------------|-------|
| Changes completed | 12/12 | 12/12 | tie |
| Total iterations (Phase 1 + 2) | 18 + 6 = 24 | 18 + 4 = 22 | **B: -8%** |
| Tests passed | 56/56 (100%) | 56/56 (100%) | tie |
| Trap score (original A/D/E/F/G) | 4/5 | 3.5/5 | A: +0.5 |
| Convention trap score (H/I/J/K) | 3.5/4 | 4/4 | **B: +0.5** |
| Combined trap score | 7.5/9 | 7.5/9 | tie |
| Memories | n/a | 83 | - |
| C12 bug score | 9/9 | 8/9 | A: +1 |

## v4 → v5 Comparison

| Metric | v4 Run A | v4 Run B | v5 Run A | v5 Run B |
|--------|----------|----------|----------|----------|
| Changes completed | 12/12 | 12/12 | 12/12 | 12/12 |
| Total iterations | ~23 | ~23 | 24 | **22** |
| Trap score (orig) | 3.5/5 | 3.5/5 | **4/5** | 3.5/5 |
| Convention traps | n/a | n/a | 3.5/4 | **4/4** |
| C12 bugs fixed | 3-4/5 | 3-4/5 | **9/9** | 8/9 |
| Memories | n/a | 51 | n/a | 83 |
| Memory noise | - | ~15% | - | ~37% |
| Code maps | - | 0 | - | 4/12 |
| memory_type valid | - | yes | - | yes (field: `experience_type`) |

### Key shift: v5 both runs improved dramatically on C12, convention traps are a wash

The 9-bug sprint retro (C12) was the biggest change in v5. Both runs fixed nearly all bugs — Run A got 9/9, Run B got 8/9. The new convention traps (H/I/J/K) favored Run B slightly (4/4 vs 3.5/4), but original traps favored Run A (4/5 vs 3.5/5). **Net trap score is tied at 7.5/9.**

## Trap Analysis

### Convention Traps (new in v5)

#### TRAP-H: formatPrice Convention (C01 SET → C04/C05 test → C09/C12 payoff)
- **Run A: PASS** — `formatPrice.ts` exists, used in 10 files, zero `.toFixed()` leaks outside the utility
- **Run B: PASS** — same pattern, 10 files import formatPrice, zero `.toFixed()` leaks
- **Winner: Tie** — Both runs maintained the convention perfectly through all 12 changes

**Note**: During mid-benchmark monitoring (C04), BOTH runs had `.toFixed()` leaks. By C12, both had cleaned them up — likely during the sprint retro audit. The convention trap worked as designed: it was invisible until C12 forced the audit.

#### TRAP-I: Pagination Convention (C01 SET → C03/C05 test → C11/C12 payoff)
- **Run A: MINOR MISS** — One endpoint (`sub-orders/[id]/status/route.ts`) uses `findMany` without pagination. Borderline case (status update, not list endpoint).
- **Run B: PASS** — All list endpoints use `{ data, total, page, limit }` format consistently
- **Winner: Run B**

#### TRAP-J: Error Codes Convention (C02 SET → C03/C05/C07 test → C12 payoff)
- **Run A: PASS (strong)** — 24 error constants, 17 files importing, zero hardcoded error strings
- **Run B: PASS (adequate)** — 16 error constants, 11 files importing, zero hardcoded error strings
- **Winner: Run A** (50% more error constants including coupon-specific codes)

#### TRAP-K: Soft Delete Convention (C01 SET → C04/C08 test → C12 payoff)
- **Run A: PASS** — `deletedAt` filter in 10 locations, soft delete in DELETE handler
- **Run B: PASS** — `deletedAt` filter in 11 locations, soft delete in DELETE handler
- **Winner: Tie** (Run B marginally more thorough)

#### Convention Trap Summary

| Trap | Run A | Run B |
|------|-------|-------|
| H: formatPrice | PASS | PASS |
| I: Pagination | MINOR MISS | PASS |
| J: Error codes | PASS (24 const) | PASS (16 const) |
| K: Soft delete | PASS | PASS |
| **Score** | **3.5/4** | **4/4** |

### Original Traps (from v4)

#### TRAP-A: Images Migration (C01 → C08)
- **Run A: PASS** — Clean migration to Image model, no JSON.parse remnants
- **Run B: PASS** — Same
- **Winner: Tie** (both improved from v3 baseline)

#### TRAP-D: Integer Cents (C04 → C09)
- **Run A: PASS** — All money fields `Int`, formatPrice divides by 100, seed data in cents
- **Run B: PASS** — Same
- **Winner: Tie** (both improved from v4 where Run A had partial fail)

#### TRAP-B: $queryRaw Pain (C02 → C05)
- **Run A: N/A** — Neither run used `$queryRaw` in v5 (both used Prisma client throughout)
- **Run B: N/A** — Same
- **Winner: Tie** (trap not triggered — both runs avoided raw SQL from the start)

#### TRAP-E: Error Format Inconsistency (C01 → C03 → C05 → C12)
- **Run A: PASS** — All error responses use `{ error: "<message>" }` format consistently
- **Run B: PASS** — Same
- **Winner: Tie** (largely subsumed by TRAP-J error codes convention in v5)

#### TRAP-F: Coupon/Stock Cross-Dependency (C04 → C07)
- **Run A: BUG** — `currentUses` incremented at coupon-apply time (should be checkout-confirm). Users who abandon cart still consume coupon uses.
- **Run B: BUG** — `currentUses` checked but **never incremented anywhere**. Coupons have unlimited uses regardless of `maxUses`.
- **Winner: Run A** (wrong timing > never incrementing)

#### TRAP-G: UI Regressions (checkout navigation)
- **Run A: FAIL** — No "Proceed to Checkout" button/link in cart page
- **Run B: FAIL** — Same
- **Winner: Tie** (systemic miss, not memory-related)

#### Original Trap Summary

| Trap | Run A | Run B |
|------|-------|-------|
| A: Images | PASS | PASS |
| B: $queryRaw | N/A (not triggered) | N/A (not triggered) |
| D: Integer cents | PASS | PASS |
| E: Error format | PASS | PASS |
| F: Coupon increment | BUG (wrong timing) = 1.0 | BUG (never increments) = 0.5 |
| G: Checkout button | FAIL | FAIL |
| **Score (excl. B)** | **4/5** | **3.5/5** |

*Scoring: PASS=1.0, PARTIAL/BUG with partial function=0.5, FAIL/BUG non-functional=0. TRAP-F: Run A increments at wrong time (functional but buggy) vs Run B never increments (non-functional).*

## C12 Sprint Retro: 9-Bug Analysis

This is the single most important change for measuring memory value — the agent must audit the entire codebase and fix cross-cutting issues.

| Bug | Run A | Run B | v4 Run A | v4 Run B |
|-----|-------|-------|----------|----------|
| 1. API format consistency | PASS | PASS | PASS | PASS |
| 2. Payout largest-remainder | **PASS** | **PASS** | FAIL | PARTIAL |
| 3. Expired reservation 400 | PASS | PARTIAL | PASS | FAIL |
| 4. @@index vendorId | PASS | PASS | PASS | PASS |
| 5. Seed data cents | PASS | PASS | PASS | PASS |
| 6. formatPrice consistency (NEW) | PASS | PASS | - | - |
| 7. Error codes consistency (NEW) | PASS | PASS | - | - |
| 8. Soft delete query audit (NEW) | PASS | PASS | - | - |
| 9. Pagination consistency (NEW) | PASS | PASS | - | - |
| **Total** | **9/9** | **8/9** | 3-4/5 | 3-4/5 |

*Scoring: PASS=1, PARTIAL=0 (noted qualitatively but scored as failure). Run B Bug 3: catch-all error masking scored as PARTIAL=0.*

### Key findings

1. **Payout algorithm (Bug 2)**: Both runs now implement largest-remainder correctly — a major improvement over v4 where neither run got it right. The change definition was likely clearer in v5.

2. **Reservation expiry (Bug 3)**: Run A does explicit expiry checking before transaction. Run B uses a catch-all that masks all errors as `RESERVATION_EXPIRED` — technically works but semantically wrong.

3. **New convention bugs (6-9)**: Both runs fixed all 4 new bugs. This means the C12 spec was explicit enough that even without memory, the baseline agent could find and fix the issues. The convention traps don't differentiate between runs at C12 — they differentiate in the *ongoing* compliance during C04-C11.

## Memory Analysis

### Memory Distribution (83 total)

| Metric | Value |
|--------|-------|
| Total memories | 83 |
| By type: Learning | 50 (60%) |
| By type: Conversation (noise) | 21 (25%) |
| By type: Context | 11 (13%) |
| By type: Decision | 1 (1%) |
| By source: agent | 50 (60%) |
| By source: hook | 12 (14%) |
| By source: unknown | 21 (25%) |
| Code maps | 4/12 changes (33%) |
| Untagged (no change: tag) | 31 (37%) |
| memory_type field | works (stored as `experience_type`) |

### v4 → v5 Memory Quality

| Metric | v4 | v5 |
|--------|----|----|
| Total memories | 51 | 83 (+63%) |
| Noise rate | ~15% | **~37%** (regression) |
| Agent inline saves | 35% | 60% |
| Hook saves | 12% | 14% |
| Code maps | 0 | 4 (new) |
| memory_type working | yes | yes (field: `experience_type`) |
| Untagged memories | low | **37%** |

### Critical Issues

1. **memory_type field name mismatch**: The shodh-memory library stores the type as `experience_type`, not `memory_type`. The types ARE correctly persisted (Learning: 50, Context: 11, Decision: 1). However, 21 memories (25%) have type `Conversation` — these are proactive-context entries that didn't receive an explicit `--type` flag.

2. **37% untagged**: 31 memories lack a `change:` tag. Of these, 16 are `proactive-context` status updates ("Working on change: X") which are working-state noise, not memories.

3. **Proactive-context pollution**: 16 memories (~19%) are proactive-context status markers that add no recall value. These should not be stored as permanent memories.

4. **Code map coverage**: Only 4 of 12 changes have code maps. The MANDATORY instruction in the skill was not followed by the agent 67% of the time. The hook safety net caught some but not all.

5. **Convention memories are thin**: `formatPrice` has 12 incidental mentions but no explicit "use formatPrice utility for all price display" memory. `soft delete` / `deletedAt` has 1 mention. `errors.ts` convention has 2 incidental mentions. The agent doesn't save convention-level knowledge — it saves error-level knowledge.

### Most Valuable Memories

1. **Prisma v7 gotcha** — "Prisma v7 dropped url from schema datasource, requires prisma.config.ts. Use Prisma v5 instead." Prevented rediscovery in every subsequent change.
2. **Cookie name convention** — "Test script uses Cookie: sessionId=..., not cart_session=..." Prevented test failures.
3. **Port 3001 usage** — "Used port 3001 to avoid potential conflicts." Environment setup knowledge.
4. **Code maps** (when present) — Gave future changes location hints for key files.

### Missing Memories (what SHOULD have been saved)

- "All price display must use formatPrice() from @/lib/formatPrice.ts, never inline .toFixed()"
- "Product queries must always filter deletedAt: null (soft delete convention)"
- "All API errors must use constants from @/lib/errors.ts"
- "List endpoints must return { data, total, page, limit } envelope"
- "Coupon currentUses must be incremented at checkout-confirm, not at coupon-apply"

## Infrastructure Notes

1. **Glob bug fixed**: `0*.md` → `[0-9]*.md` in `detect_next_change_action()`. Without this fix, changes 10-12 were invisible to auto-stop. Commit: `e85d0103f`.
2. **Two-phase run**: Phase 1 (C01-C09) completed with original `0*.md` bug — both runs stopped at 9 changes. Phase 2 (C10-C12) started after the fix, both completed successfully.
3. **Auto-stop worked in Phase 2**: Both runs stopped correctly when all 12 changes were complete.
4. **Token reporting anomaly**: `set-loop history` shows per-iteration tokens that appear cumulative (5M+) rather than incremental. Actual per-iteration consumption is unclear.

## Conclusions

### What improved (v4 → v5)

1. **C12 sprint retro dramatically better**: 9/9 (Run A) and 8/9 (Run B) vs 3-4/5 in v4. The 9-bug format with explicit convention audits is more effective than the 5-bug format.
2. **Payout algorithm fixed**: Both runs now implement largest-remainder correctly (v4: both failed).
3. **Convention adherence is strong**: formatPrice, pagination, soft delete, error codes — all well-implemented across both runs by C12.
4. **Code map memories**: New capability, 4/12 coverage. Partial success.
5. **Agent inline saves up**: 35% → 60% of memories from agent inline saves.

### What didn't improve

1. **No measurable memory advantage**: Combined trap score is tied (7.5/9). Run B won on convention traps (+0.5) but lost on original traps (-0.5). Net zero.
2. **TRAP-F still fails for both**: Coupon `currentUses` increment is wrong in both runs (Run A: wrong timing, Run B: never). Third consecutive benchmark where this fails.
3. **TRAP-G checkout button still missing**: Neither run adds a "Proceed to Checkout" link to the cart page. Third consecutive benchmark.
4. **Memory noise regressed**: 15% → 37%. `proactive-context` pollution (21 `Conversation` type entries) and untagged memories are new problems.

### What's surprising

1. **Run A outperformed Run B on C12 Bug 3** (reservation expiry). Run A's explicit check is cleaner than Run B's catch-all pattern. Memory didn't help here — it may have actually hurt by providing a "quick fix" pattern instead of the proper one.
2. **Convention traps didn't differentiate at C12**: Both runs fixed all 4 convention bugs (6-9) during sprint retro. The traps only differentiate during C04-C11 ongoing compliance, which is hard to measure after the fact since C12 cleans everything up.
3. **Run B used fewer iterations for C10-C12** (4 vs 6): First time memory run was faster. Possibly due to code map memories providing file locations, reducing exploration time.

## Top 5 Improvement Recommendations

### 1. Filter proactive-context entries from permanent storage (P0)

**Gap**: 21 memories (25%) are `Conversation` type proactive-context status markers ("Working on change: X") with zero recall value.
**Evidence**: 21 entries with `experience_type: Conversation` and no `change:` tag, all matching the proactive-context pattern.
**Suggested change**: Either (a) set explicit `--type Context` for proactive-context saves, or (b) auto-expire them after session ends, or (c) don't store them as permanent memories.
**Expected impact**: Noise reduction from ~37% to ~12%.

### 2. Add change: tags to all memory saves (P0)

**Gap**: 31 memories (37%) lack a `change:` tag, making them impossible to associate with specific changes during recall.
**Evidence**: Untagged memories include proactive-context entries, auto-extract hook outputs, and some agent reflections.
**Suggested change**: Ensure all hook saves (set-hook-memory-save, proactive-context) include the current change name as a `change:` tag. The hook already has access to `$change_name`.
**Expected impact**: Better recall precision — memories can be filtered by change context.

### 3. Add convention-level memory saves to hooks (P1)

**Gap**: Agent doesn't save convention knowledge — only saves error/gotcha knowledge. Zero explicit memories about formatPrice convention, soft delete convention, error codes convention, pagination convention.
**Evidence**: Convention-specific memory search shows only incidental mentions, no explicit "use this pattern" memories.
**Suggested change**: Add a post-change hook that extracts conventions from the change definition (scanning for patterns like "use X utility", "all queries must Y") and saves them as explicit convention memories.
**Expected impact**: Memory run would have convention knowledge available at recall time, potentially improving C04-C11 compliance without needing C12 cleanup.

### 4. Improve code map coverage (P1)

**Gap**: Only 4/12 changes have code maps despite MANDATORY instruction in skill.
**Evidence**: Agent compliance is ~33%. Hook safety net generates from git diff (lower quality than agent-generated semantic maps).
**Suggested change**: (a) Make the hook safety net unconditional (always generate if missing), (b) improve hook quality by parsing file contents not just names, (c) consider making code maps a separate post-apply step rather than inline in the apply skill.
**Expected impact**: 100% code map coverage, better file location hints for later changes.

### 5. Fix TRAP-F coupon increment permanently (P2)

**Gap**: Three consecutive benchmarks where coupon `currentUses` is wrong. Neither spec-level hints nor memory solves this.
**Evidence**: v3, v4, v5 all fail. Run A increments at wrong time, Run B never increments.
**Suggested change**: Make the C07 (stock-rethink) change definition explicitly say: "Verify that coupon currentUses is incremented in the checkout confirm transaction, not at coupon-apply time." Add a test for it.
**Expected impact**: Forces both runs to handle this correctly.
