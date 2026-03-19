# SYN-04 Results (MemoryProbe v9 + post-session extraction)

**Date**: 2026-02-17
**Benchmark**: MemoryProbe v9 (10 traps, 3 categories, weighted scoring)
**Model**: Claude Opus 4.6
**Key change**: Added `post-session-save.sh` — mechanical extraction of conventions and Developer Notes corrections after each session

## Scores

```
                    Mode A    Mode B    Delta
Category A (Code-readable, weight x1):
  T1   pagination   3/ 3      3/ 3      0
  T2   fault/err    3/ 3      3/ 3      0
  T3   removedAt    2/ 2      2/ 2      0
  T5   makeId       2/ 2      2/ 2      0
  T6   ok:true      3/ 3      3/ 3      0
  ── A subtotal    13/13     13/13      0

Category B (Code + memory nuance, weight x2):
  T4   fmtDate      2/ 2      2/ 2      0
  ── B subtotal     2/ 2      2/ 2      0

Category C (Memory-only, weight x3):
  T7   err.code     0/ 3      3/ 3    +3  ★
  T8   result-key   0/ 3      2/ 3    +2  ★
  T9   batch-POST   1/ 1      1/ 1      0
  T10  order        0/ 2      0/ 2      0
  ── C subtotal     1/ 9      6/ 9    +5

Weighted Score:
  Mode A:  20/44  (45%)
  Mode B:  35/44  (79%)
  Delta:  +15pts (+34%)  ★★★
```

## Verdict: +34% Delta — Memory Works

First successful MemoryProbe run with measurable delta. Category C (memory-only conventions) shows clear separation.

### What Worked

**T7 (dot.notation error codes): 0/3 → 3/3**
The C02 Developer Notes correction "switch from SCREAMING_SNAKE to dot.notation starting C03" was saved by post-session extraction and recalled by C03-C05 agents. All three changes used `event.not_found` style codes instead of `EVT_NOT_FOUND`.

**T8 (result key wrapping): 0/3 → 2/3**
The correction "wrap entity data in a result key" was applied in C03 and C05. C04 (dashboard) missed it — likely because dashboard endpoints feel different from entity CRUD.

**T9 (batch POST body): 1/1 → 1/1**
Both modes passed. Mode A passes because the C05 change file explicitly mentions POST for bulk operations. Not a memory signal.

### What Didn't Work

**T10 (order parameter): 0/2 → 0/2**
Neither mode used `?order=newest|oldest`. Both defaulted to `?sort=` or no sorting. The memory was saved but the agent didn't apply it. Possible reasons:
- The correction is phrased as advice ("for any endpoint that supports ordering...") rather than a requirement
- Dashboard/bulk endpoints don't have explicit sorting requirements in their change files
- The recall hook may not have surfaced this memory with enough prominence

### Category Analysis

| Category | Mode A | Mode B | Delta | Signal |
|----------|--------|--------|-------|--------|
| A (code-readable, x1) | 13/13 | 13/13 | 0 | Both modes read code equally well |
| B (code + memory, x2) | 2/2 | 2/2 | 0 | fmtDate discoverable from code |
| C (memory-only, x3) | 1/9 | 6/9 | +5 raw, +15 weighted | **Strong memory signal** |

Category A: Perfect for both — confirms agents read existing code well.
Category B: Perfect for both — fmtDate is discoverable from lib/fmt.js.
Category C: **+5 raw probes, +15 weighted points** — this is the memory delta.

### Memory State

10 memories saved by post-session extraction:
- 6 from C01 (code conventions: pagination, error format, ok wrapper, IDs, dates, soft-delete)
- 4 from C02 (Developer Notes corrections: T7 dot.notation, T8 result key, T9 batch POST, T10 order)

### Comparison Across Runs

| Run | Mode A | Mode B | Delta | Root Cause |
|-----|--------|--------|-------|------------|
| SYN-01 (v7) | ~53% | ~53% | 0% | Only 4 traps, all code-readable |
| SYN-02 (v8) | 83% | 83% | 0% | Code persistence + probe leak |
| SYN-03 (v9) | 45% | 45% | 0% | Agent never saved to memory (0 remember calls) |
| **SYN-04 (v9+extraction)** | **45%** | **79%** | **+34%** | **Post-session extraction saves corrections** |

### Key Insight

The agent **never voluntarily saves to memory**. Across SYN-03 and SYN-04, zero `set-memory remember` calls were made by the agent itself, despite CLAUDE.md instructions and explicit prompt instructions. The delta only appeared when we added mechanical post-session extraction (`post-session-save.sh`).

This means:
1. **CLAUDE.md save instructions don't work** — agents prioritize implementation and ignore save steps
2. **Prompt-level save instructions don't work** — even with "IMPORTANT: save to memory", agents skip it
3. **Infrastructure must save, not agents** — the save mechanism must be external (hooks, post-session scripts)
4. **Recall works** — when memories ARE available, the recall hook successfully surfaces them and agents use the recalled conventions

### Architecture Implication for shodh-memory

The memory system needs a **save pathway that doesn't depend on agent cooperation**:
- Current: CLAUDE.md tells agent to save → agent ignores (0% compliance)
- Working: post-session script reads change files → extracts corrections → saves mechanically
- Ideal: save hook reads transcript → LLM extracts learnings → saves automatically

The recall side works well. The save side is the bottleneck.

### Next Steps

1. **n=3 replication**: Run SYN-04 two more times to confirm delta consistency
2. **T10 investigation**: Why doesn't the order convention stick? Check if recall surfaces it
3. **Save hook enhancement**: Make `set-hook-memory-save` extract Developer Notes from project files
4. **Mode C comparison**: Run with pre-seeded memories (10 perfectly crafted memories) as upper bound
