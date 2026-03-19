# SYN-07 Results (C-first protocol, hook validation)

**Date**: 2026-02-20
**Benchmark**: MemoryProbe v2 (10 traps, 3 categories, weighted scoring)
**Model**: Claude Opus 4.6
**Run mode**: C-first protocol (Mode C first, then Mode A if recall works)
**Purpose**: Validate hook-driven recall after set-deploy-hooks fixes, test C-first benchmark protocol

## What Changed Since SYN-06

1. **C-first protocol**: Ran Mode C (pre-seeded recall, C03-C05 only) first to validate recall, then Mode A for comparison
2. **init.sh fix**: Mode C was missing `set-deploy-hooks` deployment — fixed during this run
3. **Hook updates**: `set-deploy-hooks` can now downgrade stale configs, raw-conversation-ingest replaces Haiku extraction

## Scores (inline test results)

**IMPORTANT**: score.sh produces false-negative 17% due to server event loop exit bug. All scores below are from inline test results during run.sh execution.

```
                    Mode A      Mode C      Delta
                    (baseline)  (pre-seed)
─────────────────────────────────────────────────
Category A (x1):   11/13       11/13       0
Category B (x2):    9/9         9/9        0
Category C (x3):    3/3         3/3        0
Category D (x2):    5/5         5/5        0
Category E (x3):    3/3         3/3        0
─────────────────────────────────────────────────
Weighted:          57/59 (97%) 57/59 (97%) 0%
Unweighted:        31/33 (94%) 31/33 (94%) 0%
```

## Per-Session Times

| Session | Mode A | Mode C | Notes |
|---------|--------|--------|-------|
| S01 | 94s | n/a | Mode C skips S01-S02 |
| S02 | 159s | n/a | |
| S03 | 168s | 442s | Mode C 2.6x slower (no existing code) |
| S04 | 288s | 309s | Similar |
| S05 | 202s | 230s | Similar |
| **Total** | **952s (15m)** | **1006s (16m)** | |
| **S03-S05** | **658s** | **981s** | Mode C 49% slower |

## Token Usage

| Session | Mode A turns | Mode A tokens | Mode C turns | Mode C tokens | Delta |
|---------|-------------|---------------|-------------|---------------|-------|
| S01 | 28 | 775K | n/a | n/a | - |
| S02 | 43 | 1,408K | n/a | n/a | - |
| S03 | 52 | 1,786K | **79** | **2,344K** | **C: +31%** |
| S04 | 47 | 1,621K | 47 | 1,734K | C: +7% |
| S05 | 42 | 1,368K | **31** | **1,024K** | **C: -25%** |
| **S03-S05** | **141** | **4,775K** | **157** | **5,102K** | **C: +7%** |
| **All** | **212** | **6,958K** | **157** | **5,102K** | **C: -27%** |

### Token analysis

- **S03-S05 (comparable sessions): Mode C used 7% MORE tokens** — the opposite of SYN-06's -20% saving
- **S03 cold start penalty**: Mode C spent 2,344K on S03 (vs 1,786K) because there's no C01-C02 codebase. The agent builds everything from scratch while applying conventions from memory — 79 turns vs 52
- **S05 is the one bright spot**: Mode C used 25% fewer tokens on bulk operations. Memory-recalled conventions (bulk max 100, nanoid(16), body-parser limit) applied directly without code searching
- **Total comparison is unfair**: Mode C's -27% is because it skips S01-S02 entirely (2,183K saved). This is a structural advantage of Mode C (recall-only), not a memory efficiency gain
- **vs SYN-06**: SYN-06 Mode B used -20% fewer tokens than Mode A across all sessions. That comparison was fair (both ran S01-S05). The difference: Mode B had code + memory, Mode C has only memory. Code absence hurts more than memory helps

### Why no token savings (unlike SYN-06)?

In SYN-06, Mode B had both code AND memory — the agent could recall conventions AND verify them in code, reducing exploration. In Mode C, there's no code to verify against, so the agent explores more in S03 (79 turns vs 52). The memory provides the "what" but not the "where" — without existing code, the agent still needs many turns to create everything.

**Conclusion**: Memory's token efficiency benefit requires existing code as context. Pre-seeded recall alone (Mode C) is slower because the agent lacks the codebase to anchor its implementation. A fair token comparison needs Mode B vs Mode A (both with code).

## Per-Probe Detail

| Probe | Cat | Mode A | Mode C | Notes |
|-------|-----|--------|--------|-------|
| A1 pagination (x5) | A | 5/5 | 5/5 | Both read code |
| A2 ID prefix (x4) | A | 2/4 | 2/4 | cmt_ and ntf_ missed in both |
| A3 ok wrapper (x3) | A | 3/3 | 3/3 | Both read code |
| A4 date helper (x1) | A | 1/1 | 1/1 | Both read lib/fmt.js |
| B1 dot.notation (x3) | B | 3/3 | 3/3 | Mode A reads C02 code |
| B2 result key (x3) | B | 3/3 | 3/3 | Mode A reads C02 code |
| B3 order param (x2) | B | 2/2 | 2/2 | **First time B3 passes in both!** |
| B4 removedAt (x1) | B | 1/1 | 1/1 | Both read schema |
| C1 busy_timeout (x1) | C | 1/1 | 1/1 | Mode A reads db/setup.js |
| C2 nanoid(16) (x1) | C | 1/1 | 1/1 | Mode A reads existing batch IDs |
| C3 body-parser (x1) | C | 1/1 | 1/1 | Mode A reads router config |
| D1 flat categories (x1) | D | 1/1 | 1/1 | Both read schema |
| D2 db query layer (x3) | D | 3/3 | 3/3 | Both follow pattern |
| D3 no try-catch (x1) | D | 1/1 | 1/1 | Both follow middleware pattern |
| E1 ISO 8601 (x1) | E | 1/1 | 1/1 | Mode A reads existing responses |
| E2 bulk max 100 (x1) | E | 1/1 | 1/1 | C05 spec mentions limits |
| E3 list max 1000 (x1) | E | 1/1 | 1/1 | Mode A applies same pattern |

## Key Findings

### 1. DELTA = ZERO — Benchmark does not differentiate

Mode A and Mode C achieve identical 97% weighted scores. Memory recall works perfectly (Mode C confirms this), but provides **no measurable advantage** because the baseline agent reads conventions from existing code.

### 2. Root cause: Code persistence defeats memory

The benchmark's "code-invisible" probes (C1-C3, E1-E3) are **not actually code-invisible** after C02:

```
C02 Developer Notes → Agent implements them into code →
C03-C05 agent reads the code → Conventions are visible →
Memory is redundant
```

Specifically:
- **C1 busy_timeout**: Set in `db/setup.js` — any agent reading DB setup sees it
- **C2 nanoid(16)**: Used in existing batch ID generation — any agent reading `lib/` sees it
- **C3 body-parser limit**: Set in router — any agent reading route files sees it
- **E1 ISO 8601**: Existing API responses use ISO format — agent follows pattern
- **E2 bulk max 100**: C05 spec explicitly mentions bulk limits
- **E3 list max 1000**: Agent applies same pagination cap pattern from existing code

### 3. SYN-06 baseline (45%) was likely a less-thorough C02 run

SYN-06 Mode A scored 45% — this run scored 97%. The difference is **non-deterministic C02 implementation quality**. When the C02 agent is thorough (this run), all conventions get baked into code. When it's less thorough (SYN-06), some conventions are missed and only memory agents can recover them.

### 4. B3 (order param) passes for the first time

SYN-05 and SYN-06 both showed 0/2 on B3 (order param). This run shows **2/2 PASS in both modes**. The C02 implementation included `?order=newest|oldest` support, making it code-readable.

### 5. Mode C is slower on S03 due to cold start

Mode C takes 442s on S03 vs Mode A's 168s (2.6x slower). Without C01-C02 code, the agent must build everything from scratch while also applying conventions from memory.

### 6. score.sh has a false-negative bug

The server (`node src/server.js`) starts but the event loop empties and exits immediately. score.sh gets 17% because only file-based probes pass. The inline tests (run during `run.sh`) are reliable because the agent starts and tests the server within the same session.

## C-first Protocol Assessment

The C-first protocol worked as designed:

```
Step 1: Run Mode C (15 min) → 97% weighted → GATE PASS
Step 2: Run Mode A (15 min) → 97% weighted → DELTA = 0
```

The protocol correctly identified that recall works, then the comparison revealed the benchmark design flaw. Without the C-first approach, we would have wasted time debugging a non-existent memory problem.

## Bugs Found

| Bug | Severity | Status |
|-----|----------|--------|
| init.sh Mode C missing `set-deploy-hooks` | P0 | **Fixed** |
| score.sh server exits immediately (event loop empty) | P1 | Open |
| SYN-07 baseline non-determinism (45% vs 97%) | Design | Open |

## Recommendations

### 1. Fix benchmark design: True code-invisible probes (P0)

The benchmark needs probes that **cannot be discovered from code**:
- **Negative constraints**: "Don't use try-catch in NEW route files" (existing code shows no try-catch, but it's not explicit that new code shouldn't either)
- **Rationale-dependent decisions**: "Use flat categories because hierarchical UX was tested and rejected" — code shows flat, but without memory the agent might add hierarchy if asked
- **Conflicting conventions**: C02 establishes pattern X, but C04 spec asks for something that could be done with X or Y — only memory of WHY X was chosen prevents Y
- **Cross-session debugging**: "This specific error means Z" — if the error doesn't occur in the baseline, memory can't help

### 2. Fix score.sh server exit bug (P1)

The server's event loop empties because `better-sqlite3` is synchronous — no async handles keep Node alive. Options:
- Add a `setInterval(() => {}, 1000 * 60 * 60)` keepalive
- Use `--experimental-detect-module` flag
- Fix in the test project template

### 3. Run n=3 trials to quantify non-determinism (P2)

SYN-06 baseline was 45%, SYN-07 baseline was 97%. Run 3 trials of each mode to establish variance bounds and determine if memory advantage only appears in "bad C02" runs.

## vs Previous Runs

| Run | Mode A | Mode B/C | Delta | What Changed |
|-----|--------|----------|-------|------------|
| SYN-01 | n/a | n/a | ~0% | Pre-v8, different design |
| SYN-02 | 83% | 83% | 0% | Code persistence + probe leak |
| SYN-03 | 45% | 45% | 0% | Agent never saved to memory |
| SYN-04 | 45% | 38% | -7% | Tainted run |
| SYN-05 | 45% | 79% | +34% | Post-session extraction works |
| SYN-06 | 45% | 79% | +34% | Hook-driven recall |
| **SYN-07** | **97%** | **97% (C)** | **0%** | **Code persistence wins** |

The 45% baseline in SYN-05/06 was likely non-deterministic — this run's 97% baseline shows Opus 4.6 CAN implement C02 conventions thoroughly enough to make memory redundant.
