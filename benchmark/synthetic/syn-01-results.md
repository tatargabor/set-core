# SYN-01 Results — MemoryProbe Synthetic Benchmark (6 traps, flat scoring)

**Date**: 2026-02-17
**Benchmark**: MemoryProbe (LogBook API) — 5 sequential changes, 6 convention traps
**Setup**: Claude Code (Opus 4.6), `--max-turns 25`, separate session per change
**Runtime**: ~9 minutes per mode (5 sessions total)

## Convention Probe Scoring (grep on source code)

| Trap | Convention | Mode A | Mode B | Delta |
|------|-----------|--------|--------|-------|
| T1 | Pagination (`entries` + `paging`) | 2/3 | 3/3 | **+1** |
| T2 | Errors (`fault` format) | 3/3 | 3/3 | tie |
| T3 | Soft-delete (`removedAt`) | 2/2 | 2/2 | tie |
| T4 | Dates (`fmtDate()`) | 1/2 | 2/2 | **+1** |
| T5 | ID prefix (`evt_`, `cmt_`, `bat_`) | 2/2 | 2/2 | tie |
| T6 | Ok wrapper (`ok: true`) | 2/3 | 3/3 | **+1** |
| **Total** | | **12/15 (80%)** | **15/15 (100%)** | **+20%** |

## Test Results (API-level, curl-based)

| Change | Role | Mode A | Mode B |
|--------|------|--------|--------|
| C01 Event CRUD | SEED | 13/14 | 12/14 |
| C02 Tags & Filtering | GAP | 4/8 | 8/8 |
| C03 Comments & Activity | PROBE | 9/9 | 9/9 |
| C04 Dashboard & Export | PROBE | 2/14 | 14/14 |
| C05 Bulk Operations | PROBE | 1/13 | 13/13 |
| **Total** | | **29/58 (50%)** | **56/58 (97%)** |

## Session Timing

| Change | Mode A | Mode B |
|--------|--------|--------|
| C01 | 83s | 83s |
| C02 | 104s | 104s |
| C03 | 150s | 150s |
| C04 | 113s | 113s |
| C05 | 68s | 68s |
| **Total** | **559s (9.3m)** | **559s (9.3m)** |

## Analysis

### What the delta shows

Mode B (with memory) achieved **+20% on convention probes** (15/15 vs 12/15) and **+47% on functional tests** (97% vs 50%).

The functional test gap is striking: Mode A failed to implement working endpoints for C04 (Dashboard & Export) and C05 (Bulk Operations), while Mode B implemented everything. The code FILES exist in both (the agent created route files), but Mode A's C04/C05 routes were not properly mounted or had bugs.

### Convention compliance breakdown

- **T2, T3, T5**: Both modes scored identically. These conventions are either:
  - Embedded in existing infrastructure (T2: centralized error middleware, T3: schema uses `removedAt`)
  - Explicit in the code pattern (T5: `makeId()` calls visible in C01)
- **T1, T4, T6**: Mode B scored +1 each. These are conventions that require remembering the *output format* pattern across sessions.

### Design observations

1. **Convention redundancy**: Many conventions are documented in `project-spec.md`, which every agent reads. Memory provides redundant reinforcement, not unique information. This limits the maximum observable delta.
2. **Functional completeness**: The bigger signal was Mode B implementing more working features, not just applying conventions. Memory may help with overall implementation quality, not just specific patterns.
3. **Session independence**: Same wall-clock time for both modes — memory doesn't slow things down.

### Comparison with CraftBazaar v6

| Metric | CraftBazaar v6 | MemoryProbe v7 |
|--------|---------------|----------------|
| Runtime | ~4.5 hours | ~18 minutes |
| Changes | 12 | 5 |
| Scoring method | Manual + trap checks | Automated grep + curl |
| Convention delta | 0% (tie) | +20% (B wins) |
| Overall delta | A slightly better | B clearly better |
| Setup complexity | High (set-loop, workspace) | Low (init.sh, run.sh) |
| Reproducibility | Low (timing dependent) | High (deterministic scoring) |

### Caveats

- Single run (n=1). Need multiple runs for statistical significance.
- The `--max-turns 25` limit may have caused Mode A's C04/C05 failures (ran out of turns before fixing bugs), creating a confound between memory and turn budget.
- Convention probes test source code patterns, not API behavior. A more robust approach would combine both.
- Both modes read `project-spec.md` which documents all conventions. A harder test would remove explicit documentation and rely solely on code-inferred conventions.
