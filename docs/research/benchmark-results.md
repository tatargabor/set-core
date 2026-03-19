# Benchmark Results: Developer Memory for AI Agents

How much does persistent cross-session memory improve AI agent work? We ran two benchmark suites — 10 total experiments — to find out. Each experiment revealed problems that we fixed before the next run, turning the benchmarks into an iterative improvement loop for the memory system itself.

**TL;DR:** Memory produces a clear **+34% improvement** on knowledge that only exists in memory (synthetic benchmark). On realistic full-scale projects where most knowledge is also readable from code, the advantage is harder to measure — but the infrastructure is now clean enough to isolate it. The biggest surprise: agents never save to memory voluntarily. Infrastructure must do it for them.

---

## Two Benchmark Suites

### CraftBazaar (v3–v6) — Full-Scale Realism

Two autonomous agents build the same 12-change e-commerce marketplace (CraftBazaar) in parallel. One has shodh-memory enabled, the other doesn't. Both use identical tooling (set-loop, OpenSpec, Claude Opus 4.6). Each run takes ~2 hours and produces a complete Next.js + Prisma application with products, shopping cart, multi-vendor support, discounts, checkout, stock management, and more.

**What it measures:** End-to-end impact across 12 sequential changes with cascading decisions, hidden quality traps, and a final sprint-retro (C12) that audits the entire codebase for cross-cutting bugs.

**Scoring:** Manual evaluation of "traps" — subtle quality issues that emerge when early decisions cascade into later changes. Each trap is scored PASS (1.0), PARTIAL (0.5), or FAIL (0).

### MemoryProbe Synthetic (SYN-01–SYN-05) — Controlled Isolation

Five small API changes (LogBook — an event tracking API), each run as a **separate Claude session** with fresh context. Change 1 establishes conventions, Change 2 introduces corrections via "Developer Notes" (simulating human feedback), Changes 3–5 test whether the agent applies the corrected conventions.

```
C01 (SEED)  →  C02 (CORRECT)  →  C03 (PROBE)  →  C04 (PROBE)  →  C05 (PROBE)
 establish      human feedback     test recall     test recall     test recall
 conventions    + corrections
```

**What it measures:** Whether memory carries knowledge between isolated sessions when code alone can't. Memory is the only bridge — each session starts fresh.

**Scoring:** Automated grep-based probes on source code, weighted by category:
- **Category A (x1):** Code-readable conventions (visible in existing files)
- **Category B (x2):** Corrections that override earlier patterns (code shows the old way)
- **Category C (x3):** Forward-looking advice for features that don't exist yet

---

## Trap Design: How We Test Memory

The benchmarks use "traps" — design choices in early changes that create subtle quality issues in later changes. An agent with good cross-session memory should avoid these traps; one without memory must rediscover the right approach by reading code.

### CraftBazaar Trap Examples

#### TRAP-A: Images Migration (C01 → C08)

Change 1 stores product images as a JSON string column (`images: "[\"url1\",\"url2\"]"`). Change 8 introduces a proper `Image` model with a relation table. The trap: every page that displays images must be updated from `JSON.parse(product.images)` to `product.images.map(img => img.url)`. Missing a page causes a runtime crash.

| Version | No Memory | With Memory | Notes |
|---------|-----------|-------------|-------|
| v3 | FAIL (runtime crash) | PARTIAL (no crash, but missing feature) | Memory avoided the crash |
| v4 | PASS | PASS | Both improved |
| v5–v6 | PASS | PASS | Stable |

#### TRAP-F: Coupon/Stock Cross-Dependency (C04 → C07)

Change 4 adds discount coupons with `currentUses` / `maxUses` tracking. Change 7 rethinks stock management. The trap: `currentUses` must be incremented inside the checkout-confirm transaction — not at coupon-apply time (users who abandon cart would consume coupon uses) and not never (unlimited coupons regardless of `maxUses`).

| Version | No Memory | With Memory | Notes |
|---------|-----------|-------------|-------|
| v3 | PASS | PARTIAL (never increments) | |
| v4 | PARTIAL (never increments) | PARTIAL (never increments) | Both miss it |
| v5 | BUG (wrong timing) | BUG (never increments) | Still broken |
| v6 | **PASS** | **PASS** | Fixed via explicit spec requirement |

This trap failed for 3 consecutive benchmarks until we added an explicit requirement: "Coupon currentUses MUST be incremented inside the checkout-confirm transaction." Once the spec was unambiguous, both agents got it right. **Lesson:** Some "traps" are really spec ambiguity, not memory gaps.

#### TRAP-G: Checkout Navigation (C02 → all later changes)

Change 2 creates a shopping cart page. Every subsequent change that adds items, discounts, or checkout functionality assumes the cart has a "Proceed to Checkout" button. Neither agent ever adds one.

| v3 | v4 | v5 | v6 |
|----|----|----|-----|
| Both FAIL | Both FAIL | Both FAIL | Both FAIL |

Four consecutive benchmarks, zero passes. This is a **spec blind spot** — the requirement seems obvious to humans but is never explicitly stated. Neither memory nor code-reading helps because there's nothing to remember or read.

#### Convention Traps (v5+): formatPrice, Pagination, Error Codes, Soft Delete

Starting in v5, we added convention traps that test whether agents maintain cross-cutting patterns consistently:

| Trap | Convention | What breaks if violated |
|------|-----------|------------------------|
| H: formatPrice | All price display uses `formatPrice()` utility | Inline `.toFixed(2)` on cents gives wrong values |
| I: Pagination | All list endpoints return `{data, total, page, limit}` | Inconsistent API responses |
| J: Error Codes | All errors use constants from `errors.ts` | Hardcoded strings, no i18n, inconsistent codes |
| K: Soft Delete | All queries filter `deletedAt: null` | Deleted records appear in listings |
| L: Responsive | All pages use `ResponsiveContainer` | Pages break on mobile |

#### Drift Traps (v6): Pagination UI, Toast Notifications

v6 added "drift traps" — testing whether shared UI components stay consistent as the codebase grows:

| Trap | What drifts | v6 No Memory | v6 With Memory |
|------|-------------|--------------|----------------|
| M: Pagination UI | Some pages use shared `<Pagination>`, others roll their own | PASS | PARTIAL (imported but not rendered) |
| N: Toast | Some pages mount Toast locally instead of global layout | PASS (global mount) | PARTIAL (per-page mount) |

Surprisingly, the drift traps (designed to favor memory) actually favored the baseline. The memory agent "knew" what existed but didn't verify completeness; the baseline agent's exhaustive search found the right architecture.

### Synthetic Trap Examples

#### T7: Error Code Format (dot.notation vs SCREAMING_SNAKE)

Change 1 establishes `SCREAMING_SNAKE` error codes (e.g., `EVT_NOT_FOUND`). Change 2's Developer Notes say: "Starting in C03, switch to `dot.notation` (e.g., `event.not_found`)." The correction is never applied to C02 code — it's forward-looking advice.

Without memory, C03–C05 agents read C01/C02 code, see `EVT_NOT_FOUND`, and copy it. With memory, they recall the correction and use `event.not_found`.

| Run | Mode A | Mode B | Delta |
|-----|--------|--------|-------|
| SYN-03 | 0/3 | 0/3 | 0 (agent never saved the correction) |
| SYN-04 | 0/3 | **3/3** | +3 (post-session extraction saved it) |
| SYN-05 | 0/3 | **3/3** | +3 (confirmed) |

#### T8: Response Nesting (flat vs wrapped)

Change 2 advises: "Wrap entity data in a `result` key: `{ok: true, result: {entries, paging}}`" instead of flat format. Without memory, agents use the flat format they see in C01 code.

| Run | Mode A | Mode B | Delta |
|-----|--------|--------|-------|
| SYN-04 | 0/3 | 2/3 | +2 (C04 dashboard missed it) |
| SYN-05 | 0/3 | 2/3 | +2 (same pattern — dashboard endpoints feel "different") |

#### T10: Sort Parameter (the trap that never works)

Change 2 advises using `?order=newest|oldest` instead of `?sort=asc|desc`. Neither mode ever applies this — across SYN-04 and SYN-05, both score 0/2. The memory exists but the agent doesn't apply it, likely because the advice is phrased as a suggestion ("for any endpoint that supports ordering...") rather than a hard requirement.

---

## Results

### CraftBazaar (v3–v6)

| Version | Date | Trap Score (No Memory) | Trap Score (Memory) | Memory Delta | Noise | Memories |
|---------|------|------------------------|---------------------|--------------|-------|----------|
| **v3** | 2026-02-16 | 4.0/5 | 1.5/5 | **-2.5 (hurt)** | 27% | 66 |
| **v4** | 2026-02-16 | 3.5/5 | 3.5/5 | 0 (tied) | ~15% | 51 |
| **v5** | 2026-02-16 | 7.5/9 | 7.5/9 | 0 (tied) | 37% | 83 |
| **v6** | 2026-02-17 | 11.5/13 | 11/13 | **-0.5** | **0%** | 57 |

#### C12 Sprint-Retro (the most important change)

C12 is a codebase-wide audit that fixes cross-cutting bugs. It's the best single measurement of whether memory helps with complex, multi-file changes.

| Bug | v3 A/B | v4 A/B | v5 A/B | v6 A/B |
|-----|--------|--------|--------|--------|
| API format consistency | P/F | P/P | P/P | P/P |
| Payout largest-remainder | P/F | F/P | P/P | P/P |
| Expired reservation 400 | P/P | P/F | P/P | P/P |
| @@index vendorId | P/P | P/P | P/P | P/P |
| Seed data cents | P/P | P/P | P/P | P/P |
| formatPrice consistency | — | — | P/P | P/P |
| Error codes consistency | — | — | P/P | P/P |
| Soft delete audit | — | — | P/P | P/P |
| Pagination API | — | — | P/P | P/P |
| Responsive layout | — | — | — | P/P |
| Pagination UI | — | — | — | P/P |
| Toast notifications | — | — | — | P/P |
| **Total** | **5 vs 3** | **3-4 vs 3-4** | **9 vs 8** | **11 vs 9** |

*(P = Pass, F = Fail, P = Partial scored as 0)*

The baseline agent consistently scored the same or better on C12. In v6, token analysis reveals why: the memory agent used 502K tokens on C12 (vs baseline's 1,023K) — memory reduced exploration time but also reduced thoroughness.

#### Convention Trap Scores (v5–v6)

| Trap | v5 No Memory | v5 Memory | v6 No Memory | v6 Memory |
|------|-------------|-----------|--------------|-----------|
| H: formatPrice | PASS | PASS | PASS | PASS |
| I: Pagination | MINOR MISS | PASS | PASS | PASS |
| J: Error codes | PASS (24 const) | PASS (16 const) | PARTIAL | **PASS** |
| K: Soft delete | PASS | PASS | PASS | PASS |
| L: Responsive | — | — | PASS | PASS |
| M: Pagination UI | — | — | PASS | PARTIAL |
| N: Toast | — | — | PASS | PARTIAL |

Error codes (TRAP-J) is the one consistent area where memory helps — the memory agent imports from `errors.ts` more consistently than the baseline.

### MemoryProbe Synthetic (SYN-01–SYN-05)

| Run | Mode A (baseline) | Mode B (memory) | Weighted Delta | Root Cause |
|-----|-------------------|-----------------|----------------|------------|
| **SYN-01** | ~80% | ~100% | ~+20% | Confounded by functional failures in Mode A |
| **SYN-02** | 83% | 83% | 0% | Code persistence — corrections baked into C02 code |
| **SYN-03** | 45% | 45% | 0% | Agent never saved to memory (0 remember calls) |
| **SYN-04** | 45% | 79% | **+34%** | Post-session extraction saves corrections |
| **SYN-05** | 45% | 79% | **+34%** | Confirmed |

#### SYN-05 Category Breakdown (final confirmed run)

| Category | Weight | Mode A | Mode B | Raw Delta | Weighted Delta |
|----------|--------|--------|--------|-----------|----------------|
| A: Code-readable | x1 | 13/13 (100%) | 13/13 (100%) | 0 | 0 |
| B: Code + nuance | x2 | 2/2 (100%) | 2/2 (100%) | 0 | 0 |
| C: Memory-only | x3 | 1/9 (11%) | 6/9 (67%) | **+5** | **+15** |
| **Total** | | **20/44 (45%)** | **35/44 (79%)** | | **+34%** |

The delta comes entirely from Category C. Category A confirms both modes read code equally well. The +34% is the isolated value of knowledge that exists **only** in memory.

#### Per-Trap Detail (SYN-05)

| Trap | Cat | Convention | Mode A | Mode B | Delta |
|------|-----|-----------|--------|--------|-------|
| T1 | A | Pagination format `{entries, paging}` | 3/3 | 3/3 | 0 |
| T2 | A | Error format `{fault: {reason, code, ts}}` | 3/3 | 3/3 | 0 |
| T3 | A | Soft-delete column `removedAt` | 2/2 | 2/2 | 0 |
| T4 | B | Date helper `fmtDate()` for all dates | 2/2 | 2/2 | 0 |
| T5 | A | ID prefix via `makeId()` | 2/2 | 2/2 | 0 |
| T6 | A | Success wrapper `{ok: true}` | 3/3 | 3/3 | 0 |
| **T7** | **C** | **Error codes: dot.notation** | **0/3** | **3/3** | **+3** |
| **T8** | **C** | **Response nesting: result key** | **0/3** | **2/3** | **+2** |
| T9 | C | Batch operations via POST body | 1/1 | 1/1 | 0 |
| T10 | C | Sort parameter `?order=` | 0/2 | 0/2 | 0 |

---

## How Each Benchmark Improved the Memory System

Each run revealed specific problems that we fixed before the next. The benchmarks served as an iterative improvement loop.

### CraftBazaar v3 → v4: Fixing Overconfidence

**Problem:** Memory gave +32% efficiency but crashed quality from 4.0/5 to 1.5/5. The agent was too fast — it skipped thorough code reading because memory gave it surface-level answers.

**Fixes applied:**
- **REREAD_FILES injection:** For revision changes (C07–C12), the recall hook now injects explicit file lists that the agent MUST read before implementing. Example for the sprint-retro:
  ```
  CRITICAL: You MUST re-read actual code, not rely on memory.
  RE-READ these files: src/app/api/products/route.ts, src/app/api/vendors/route.ts...
  ```
- **Reflection hook cleanup:** Added "already implemented" noise filter, `change:` tags, content dedup via semantic similarity
- **Decision hook:** Only saves when real `**Choice**` lines found (no commit message fallback)

**Result:** v4 memory quality jumped from 1.5/5 to 3.5/5 (+133%). Efficiency advantage disappeared but quality parity was achieved.

### CraftBazaar v4 → v5: Adding Convention Traps

**Problem:** v4 showed tied scores (3.5/5 both). Hard to tell if memory was helping or if both runs were equally mediocre. Needed finer-grained measurement.

**Fixes applied:**
- **4 new convention traps (H/I/J/K):** formatPrice, pagination, error codes, soft delete — testing whether agents maintain patterns across 12 changes
- **Code map memories:** New concept — save a map of which files implement what functionality, so later agents know where to look
- **9-bug sprint-retro:** C12 expanded from 5 to 9 bugs for more granular scoring

**Result:** Convention traps slightly favored memory (4/4 vs 3.5/4), but original traps slightly favored baseline (4/5 vs 3.5/5). Net: tied at 7.5/9. But noise regressed to 37% from proactive-context pollution (21 `Conversation`-type status markers).

### CraftBazaar v5 → v6: Eliminating Noise

**Problem:** 37% memory noise. 31/83 memories lacked `change:` tags. 21 were useless status markers. Code map coverage only 33%.

**Fixes applied:**
- **`auto_ingest=False`:** Stopped proactive-context status markers from being stored as permanent memories. Conversation-type noise went from 21 to 0.
- **change: tag enforcement:** All hook saves now include the current change name. Untagged went from 37% to 0%.
- **Convention extraction:** New LLM prompt addition to the transcript extraction hook — scans for cross-cutting conventions and saves them explicitly. Produced 6 convention memories (0 in v5).
- **3 new drift traps (L/M/N):** Responsive layout, pagination UI drift, toast notification drift
- **C12 expanded to 12 bugs** with explicit spec for TRAP-F coupon increment

**Result:** Noise eliminated (0%), TRAP-F finally fixed (both pass), conventions saved. But Run A still scored 11.5/13 vs Run B's 11/13. The drift traps (designed to favor memory) unexpectedly favored the baseline.

### SYN-01 → SYN-02: Discovering the Code Persistence Channel

**Problem:** SYN-01 showed +20% delta, but it was confounded — Mode A's C04/C05 endpoints didn't work (functional failure, not convention failure).

**Fixes applied:**
- Added 4 more traps (T7–T10) with weighted categories
- Separated convention scoring from functional tests

**Result:** 0% delta. Root cause: corrections applied in C02 code are readable by C03+ agents. The codebase itself acts as a memory channel.

**Key insight discovered:**
> The ONLY knowledge that differentiates memory from no-memory is knowledge that (a) was shared in a PAST session, (b) is NOT visible in any code or spec file, and (c) is relevant to a FUTURE implementation decision.

### SYN-02 → SYN-03: Preventing Code Leakage

**Problem:** Code persistence meant C02 corrections were baked into code, readable by all future agents.

**Fixes applied:**
- C02 Developer Notes now say "Starting in C03, don't apply to C02" — corrections are forward-looking only
- Convention probes removed from test scripts (moved to post-hoc `score.sh`) to prevent probe leakage through failure messages

**Result:** Still 0% delta, but for a new reason — the agent never saved anything to memory (0 `set-memory remember` calls across 5 sessions). The trap design was validated: Category A showed 45% (correct — code-readable), Category C showed 11% (correct — no memories to recall).

### SYN-03 → SYN-04: Infrastructure-Level Saving

**Problem:** Agents don't save. Despite CLAUDE.md step 8 mandating saves, despite explicit prompt instructions, the agent consumes all turns on implementation and never reaches the save step.

**Discovery: Prompts beat instructions.** The agent follows the `claude -p` prompt more strictly than CLAUDE.md. If the prompt says "implement and fix tests", the agent does exactly that — nothing more.

**Fixes applied:**
- **`post-session-save.sh`:** A mechanical script that runs after each session, reads the change files (including Developer Notes), extracts conventions and corrections, and saves them to `set-memory`. No agent cooperation needed.
- Run prompt updated to explicitly mention CLAUDE.md workflow
- Max turns increased from 25 → 30

**Result:** **+34% weighted delta.** The post-session extraction saved the C02 corrections that the agent never would have saved voluntarily. C03–C05 agents recalled them and applied dot.notation error codes (T7: 0/3 → 3/3) and result key nesting (T8: 0/3 → 2/3).

### SYN-04 → SYN-05: Confirmation Run

**Problem:** Need to verify SYN-04 wasn't a fluke.

**Additional discovery:** Concurrent Claude CLI sessions fail — processes exit in 2-3 seconds with 0 bytes output. Sessions must run sequentially (Mode A first, then Mode B).

**Result:** Identical +34% delta. Same per-trap pattern (T7: +3, T8: +2, everything else tied).

---

## Memory Quality Evolution

### CraftBazaar Memory Stats

| Metric | v3 | v4 | v5 | v6 |
|--------|----|----|----|----|
| Total memories | 66 | 51 | 83 | 57 |
| Noise rate | 27% | ~15% | 37% | **0%** |
| Agent inline saves | 8% | 35% | 60% | 61% |
| Hook saves | 6% | 16% | 14% | **39%** |
| Convention memories | 0 | 0 | 0 | **6** |
| Code maps | 0 | 0 | 4/12 | 2/12 |
| Untagged | high | low | 37% | **0%** |
| With change: tag | — | — | 63% | **100%** |

### Most Valuable Memory Types

From v3–v6, these memories consistently provided the most value:

**Environment gotchas** (saved rediscovery in every subsequent change):
- "Prisma v7 dropped url from schema datasource, requires prisma.config.ts. Use Prisma v5 instead."
- "Used port 3001 to avoid potential conflicts."
- "Stale .next cache causes 404 on new routes — always rm -rf .next"

**Test expectations** (prevented debugging loops):
- "Test cookie name is 'sessionId' not 'cart-session-id'"
- "Product listing must use id:asc ordering for test stability"

**Conventions** (v6, from automated extraction):
- "All models must include deletedAt field for soft-delete; queries must filter deletedAt IS NULL"
- "All list endpoints use { data, total, page, limit } format"
- "When migrating from denormalized to normalized data models, API response shape should remain stable"

### Memories That Were Missing

These should have been saved but weren't (agents don't save convention-level knowledge):
- "All price display must use formatPrice() from @/lib/formatPrice.ts, never inline .toFixed()"
- "Coupon currentUses must be incremented at checkout-confirm, not at coupon-apply"
- "Toast component must be mounted once in layout.tsx, not per-page"

---

## Key Findings

### 1. Recall works; save is the bottleneck

Across all synthetic runs (SYN-03, SYN-04, SYN-05), agents made **zero voluntary `set-memory remember` calls** despite:
- CLAUDE.md step 8 mandating saves
- run.sh prompt explicitly requesting saves ("IMPORTANT: save project conventions...")
- 30 available turns per session

Agents consume all turns on implementation and test-fix loops. Saving is treated as optional and always skipped. The only working save mechanisms are infrastructure-level: post-session extraction scripts and automated hooks.

**Implication for system design:** The save pathway must not depend on agent cooperation. Infrastructure (hooks, post-session scripts, transcript extraction) must handle saving. The agent's job is to recall and use — not to save.

### 2. Code is a memory channel

In a persistent codebase, conventions established in Change 1 are readable in Change 5. SYN-02 proved this definitively: corrections applied in C02 code were picked up by C03–C05 agents, producing 0% delta despite memory being available.

Memory only adds unique value for knowledge that isn't in code:
- **Corrections** that override earlier patterns (the code shows the old way)
- **Decisions** with rationale (why we chose X over Y)
- **Environmental gotchas** (framework versions, port conflicts, cookie names)
- **Forward-looking advice** for features that don't exist yet

### 3. Memory can reduce thoroughness

CraftBazaar v6 token analysis: the memory agent used **502K tokens** on the C12 sprint-retro vs the baseline's **1,023K tokens**. Memory halved exploration time — but also halved thoroughness. The memory agent's C12 implementations had:
- Toast mounted per-page instead of globally
- Pagination component imported but not rendered on some pages
- Reservation expiry logic with false positives

**The overconfidence hypothesis:** Memory provides shortcuts ("I know what files exist") that bypass the exhaustive code reading needed for cross-cutting changes. The baseline agent's brute-force grep-everything approach produced cleaner architecture.

**The fix:** Recall-then-verify — treat memories as starting points, always grep to confirm current state.

### 4. Clean infrastructure is a prerequisite

The v3→v6 progression was mostly about cleaning up the memory pipeline:

| Problem | When found | Fix | Effect |
|---------|-----------|-----|--------|
| 27% noise from reflection loop | v3 | "Already implemented" filter, dedup | Noise: 27% → 15% |
| Agent inline saves only 8% | v3 | Stronger CLAUDE.md instructions | Saves: 8% → 35% |
| Proactive-context pollution | v5 | `auto_ingest=False` | Conversation noise: 25% → 0% |
| 37% untagged memories | v5 | change: tag in all hooks | Untagged: 37% → 0% |
| Zero convention memories | v5 | Convention extraction in transcript hook | Conventions: 0 → 6 |

### 5. Prompts beat instructions

SYN-03 revealed a critical hierarchy: the `claude -p` prompt overrides CLAUDE.md instructions. If the prompt says "implement and fix tests", the agent does exactly that and nothing more. CLAUDE.md's "save to memory" step is treated as optional background noise.

**Implication:** Don't rely on prompt-level instructions for critical behaviors. Use infrastructure (hooks, post-session scripts) for anything that must happen reliably.

### 6. Spec clarity > memory

TRAP-F (coupon increment) failed for 3 consecutive benchmarks regardless of memory. Once the spec explicitly said "increment currentUses in the checkout-confirm transaction", both agents got it right. TRAP-G (checkout button) has failed for 4 consecutive benchmarks — it's never explicitly required.

**Implication:** Memory can't compensate for ambiguous requirements. It amplifies clear knowledge; it doesn't create clarity.

---

## Benchmark Infrastructure Lessons

### Cross-contamination risk

In v6, both runs resolved to the same shodh-memory storage path (`~/.local/share/set-core/memory/craftbazaar`) because both projects were named "craftbazaar". Run B wrote 57 memories while Run A was running concurrently. However, triple-layer isolation (no memory hooks in Run A's settings.json, no memory instructions in Run A's CLAUDE.md, no memory hooks in Run A's skills) prevented contamination.

**Fix for future runs:** Use different project names (e.g., `craftbazaar-baseline` vs `craftbazaar-memory`) for physically separate memory databases.

### Test suite weakness

CraftBazaar's test-12 (sprint-retro) passes **71% of checks with no running server** — most checks are `grep` or `[ -f ]` based, not behavioral. Specific weaknesses:

| Issue | Impact |
|-------|--------|
| Payout algorithm auto-passes when no multi-vendor orders exist | Largest-remainder was NEVER actually tested |
| `grep "Pagination"` matches `import` statements | Memory agent's "imported but not rendered" passed |
| No check for Toast in `layout.tsx` | Per-page mounts (incomplete) passed |
| Vendor regression checks skip silently | 2 checks never executed |

### Concurrent sessions don't work

Claude CLI sessions cannot run concurrently — parallel sessions exit in 2-3 seconds with 0 bytes output. Synthetic benchmark must run sequentially (Mode A first, then Mode B).

---

## What's Next

### For the memory system

1. **Unconditional code map generation.** Agent compliance on saving code maps is ~20% despite MANDATORY instructions. The hook must generate them automatically after every change using git diff + file content parsing — no agent cooperation required.

2. **Recall-then-verify pattern.** Add to memory instructions: "After recalling past implementation details, ALWAYS grep to verify current state." Addresses the overconfidence problem while preserving the efficiency benefit of recall.

3. **Richer convention extraction.** The convention extraction hook works but captures only 6 conventions in 12 changes. Needs more explicit patterns for cross-cutting rules and architectural decisions.

4. **Save pathway redesign.** Since agents never save voluntarily, the three-layer architecture (auto hooks + skill hooks + stop reminder) should shift weight toward auto hooks. Skill-level saves are unreliable; infrastructure saves are reliable.

### For the benchmarks

1. **Stronger tests.** Replace grep-based checks with behavioral checks (curl against running server, rendered output verification). Target: <30% pass rate with no server (currently 71%).

2. **n=3 replication.** SYN-04 and SYN-05 show consistent +34%, but two runs isn't sufficient for publication. Need a third run plus variance analysis.

3. **Mode C (pre-seeded recall).** Run synthetic benchmark with perfectly crafted memories injected (no save step) to measure the theoretical upper bound of recall effectiveness.

4. **Intermediate drift checks.** Add non-failing convention checks to intermediate test scripts. Currently drift is only measurable at C12 — need data on when and how conventions erode during C04–C11.

5. **Fix TRAP-G permanently.** Add explicit "Proceed to Checkout" button requirement to C02. Four consecutive failures prove the spec needs to say it.

---

## Summary

### The headline numbers

| Benchmark | No Memory | With Memory | Delta |
|-----------|-----------|-------------|-------|
| **Synthetic (memory-only knowledge)** | 45% | 79% | **+34%** |
| **Full-scale (realistic project)** | 11.5/13 | 11/13 | -0.5 (no advantage yet) |

### What we proved

1. **Memory recall works.** When the right knowledge is in the memory store, agents use it and produce measurably better code (+34% on memory-only knowledge).

2. **Agents don't save.** Zero voluntary saves across 15+ sessions. Infrastructure must handle saving.

3. **Code-readable knowledge doesn't need memory.** Convention traps visible in existing code show 0% delta — agents read code well.

4. **Memory can cause overconfidence.** The memory agent explores less (half the tokens on C12) but produces lower quality. Needs a verify-after-recall pattern.

5. **Clean infrastructure matters.** Noise reduction (27% → 0%), proper tagging (0% → 100%), and convention extraction (0 → 6) were all prerequisites for useful memory.

### The gap to close

The synthetic benchmark proves the mechanism works. The full-scale benchmark shows the mechanism doesn't yet produce advantage on realistic projects — because most knowledge in a persistent codebase is code-readable. The next step is improving what gets saved (code maps, conventions, architectural decisions) and how it gets used (recall-then-verify instead of recall-then-trust).

---

*Last updated: 2026-02-17. Detailed per-run results: `benchmark/v3-results.md` through `v6-results.md` (CraftBazaar), `benchmark/synthetic/syn-01-results.md` through `syn-05-results.md` (MemoryProbe).*
