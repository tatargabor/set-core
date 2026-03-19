# SYN-05 Results (MemoryProbe v9 + post-session extraction)

**Date**: 2026-02-17
**Benchmark**: MemoryProbe v9 (10 traps, 3 categories, weighted scoring)
**Model**: Claude Opus 4.6
**Run mode**: Sequential (concurrent CLI runs fail — sessions exit immediately)

## Scores

```
                    Mode A      Mode B      Delta
                    (baseline)  (memory)
─────────────────────────────────────────────────
Category A (x1):   13/13       13/13       0
Category B (x2):    2/2         2/2        0
Category C (x3):    1/9         6/9       +5
─────────────────────────────────────────────────
Weighted:          20/44 (45%) 35/44 (79%) +34%
Unweighted:        16/24 (66%) 21/24 (87%) +21%
```

## Per-Trap Detail

| Trap | Cat | Mode A | Mode B | Delta | Notes |
|------|-----|--------|--------|-------|-------|
| T1 pagination | A | 3/3 | 3/3 | 0 | Both read code |
| T2 fault/error | A | 3/3 | 3/3 | 0 | Both read code |
| T3 removedAt | A | 2/2 | 2/2 | 0 | Both read code |
| T4 fmtDate | B | 2/2 | 2/2 | 0 | Both read code + lib |
| T5 makeId | A | 2/2 | 2/2 | 0 | Both read code |
| T6 ok:true | A | 3/3 | 3/3 | 0 | Both read code |
| **T7 err.code** | **C** | **0/3** | **3/3** | **+3** | **Memory recalled dot.notation correction** |
| **T8 result key** | **C** | **0/3** | **2/3** | **+2** | **Memory recalled nesting correction** |
| T9 batch POST | C | 1/1 | 1/1 | 0 | C05 spec says POST explicitly |
| T10 order param | C | 0/2 | 0/2 | 0 | Neither applied order convention |

## Key Finding: +34% Weighted Delta

**The memory system produces measurable improvement on memory-only knowledge.**

- Category A (code-readable): 0% delta — both modes discover conventions from existing code
- Category B (nuance): 0% delta — both modes discover fmtDate from lib/fmt.js
- Category C (memory-only): +5 out of 9 probes, +15 weighted points

The delta comes entirely from T7 (dot.notation) and T8 (result key) — corrections that exist ONLY in C02 Developer Notes and were saved to memory by the post-session extraction. Without memory, the agent uses C01's SCREAMING_SNAKE error codes and flat response format.

## What Worked

1. **Post-session extraction** (`post-session-save.sh`): After each session, extracts Developer Notes corrections and code conventions, saves to memory. This ensures critical knowledge gets saved even when the agent runs out of turns.

2. **Memory recall**: C03-C05 agents successfully recalled conventions from memory (3-4KB recall results per query).

3. **Trap design**: Category A/B/C separation validated — zero delta on code-readable traps, significant delta on memory-only traps.

## What Didn't Work

1. **T10 (order param)**: Neither mode used `?order=newest|oldest`. The memory contains the correction but the agent didn't apply it. Possible cause: the order convention is more "advice" than "correction" — it says "for any endpoint that supports ordering" but doesn't specify which endpoints those are.

2. **T8 C04 miss**: Mode B missed the result key on C04 dashboard endpoints (passed C03 and C05). Inconsistent application of recalled knowledge.

3. **Agent-driven save**: Despite CLAUDE.md mandating memory saves (step 8) and the run.sh prompt explicitly mentioning it, the agent STILL used zero `set-memory remember` calls. The post-session extraction was essential.

## Architecture Note

The post-session extraction is a legitimate mechanism — it represents automated extraction of structured knowledge from development artifacts (change files, code review notes). The benchmark tests whether having that knowledge available via recall improves implementation quality.

The comparison is:
- **Mode A**: Agent reads code + spec → implements from scratch
- **Mode B**: Agent reads code + spec + recalled memories → implements with historical context

## SYN-05 vs Previous Runs

| Run | Mode A | Mode B | Delta | Root Cause |
|-----|--------|--------|-------|------------|
| SYN-01 | n/a | n/a | ~0% | Pre-v8, different design |
| SYN-02 | 83% | 83% | 0% | Code persistence + probe leak |
| SYN-03 | 45% | 45% | 0% | Agent never saved to memory |
| SYN-04 | 45% | 38% | -7% | Tainted (mid-run fix, concurrent failure) |
| **SYN-05** | **45%** | **79%** | **+34%** | **Post-session extraction works** |

## Next Steps

- Run n=3 trials for statistical confidence
- Investigate T10 miss (agent doesn't apply order convention despite having it in memory)
- Consider Mode C (pre-seeded, recall-only) baseline to isolate recall effectiveness
