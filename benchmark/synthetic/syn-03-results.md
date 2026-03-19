# SYN-03 Results (MemoryProbe v9)

**Date**: 2026-02-17
**Benchmark**: MemoryProbe v9 (10 traps, 3 categories, weighted scoring)
**Model**: Claude Opus 4.6

## Scores

```
Scoring: MemoryProbe v9 (10 traps, 3 categories, weighted scoring)

Category A (Code-readable, weight x1):
  T1   pagination 3/ 3      3/ 3     0
  T2   fault/err  3/ 3      3/ 3     0
  T3   removedAt  1/ 2      1/ 2     0
  T5   makeId     2/ 2      2/ 2     0
  T6   ok:true    3/ 3      3/ 3     0
  ── A subtotal   12/13     12/13    0

Category B (Code + memory nuance, weight x2):
  T4   fmtDate    1/ 2      1/ 2     0
  ── B subtotal   1/ 2      1/ 2     0

Category C (Memory-only, weight x3):
  T7   err.code   0/ 3      0/ 3     0
  T8   result-key 0/ 3      0/ 3     0
  T9   batch-POST 1/ 1      1/ 1     0
  T10  order      0/ 2      0/ 2     0
  ── C subtotal   1/ 9      1/ 9     0

Weighted Score: Mode A: 20/44 (45%)  Mode B: 20/44 (45%)  Delta: 0%
```

## Verdict: 0% Delta — Memory System Did Not Save

### Design Changes from SYN-02

SYN-03 fixed two SYN-02 root causes:
1. **Code persistence** — C02 Developer Notes now say "Starting in C03, don't apply to C02." C02 code keeps SCREAMING_SNAKE error codes and flat response format.
2. **Probe info leak** — Convention probes removed from test scripts (only in score.sh now).

These fixes worked: Category A dropped from ~83% to 45% (probes no longer leaking), and Category C dropped from 78% to 11% (code no longer carries corrections). **The trap design is correct.**

### Root Cause: Zero Memory Saves

Post-mortem transcript analysis reveals **zero `set-memory remember` calls** across all 5 Mode B sessions:

| Session | `recall` calls | `remember` calls | Memories saved |
|---------|---------------|-------------------|----------------|
| C01     | 0*            | 0                 | 0              |
| C02     | 3             | 0                 | 0              |
| C03     | 3             | 0                 | 0              |
| C04     | 3             | 0                 | 0              |
| C05     | 3             | 0                 | 0              |

*C01 has 1 `set-memory` mention (likely recall from CLAUDE.md step 1)

The agent followed CLAUDE.md steps 1-7 (recall, read, implement, test) but never reached step 8 (save). With `--max-turns 25`, all turns were consumed by implementation and test-fix loops.

### Contributing Factors

1. **Run prompt omission**: The `run.sh` prompt says "Implement... fix failures... Do not proceed." It doesn't mention saving. The agent follows the prompt, not the CLAUDE.md step 8.
2. **Turn budget exhaustion**: 25 max-turns is barely enough for implementation. The agent has no turns left for saving after fixing test failures.
3. **Save hook mismatch**: `set-hook-memory-save` only extracts from openspec design.md files or opsx-skill transcripts. The benchmark uses neither.
4. **Passive save instruction**: CLAUDE.md step 8 says "save important patterns" but the run.sh prompt doesn't reinforce this. The agent treats saving as optional.

### Fixes for SYN-04

1. **Run.sh prompt**: Mode B prompt now explicitly says "Follow the workflow in CLAUDE.md" and "IMPORTANT: After tests pass, follow CLAUDE.md step 8 — save project conventions, corrections, and Developer Notes advice to memory"
2. **Max turns**: Increased from 25 → 30 to give room for saving
3. **CLAUDE.md save step**: Step 8 now says "you MUST save" (mandatory), emphasizes Developer Notes corrections, and requires 2-3 memories per session
4. **Memory guidelines**: Added explicit mention of Developer Notes corrections as always worth saving

### Lessons

- **Prompts beat instructions**: Agent follows the `claude -p` prompt more strictly than CLAUDE.md. If the prompt doesn't mention saving, the agent won't save.
- **Turn budgets matter**: 25 turns is tight for implement + test + save. Budget for saving when counting turns.
- **Save hooks are workflow-specific**: The current save hook is designed for opsx/openspec workflows, not generic benchmark scenarios.
- **Trap design validated**: Despite 0% delta, the trap categories are correct — Category A gets discovered from code, Category C stays hidden. The problem is on the save side, not the probe side.
