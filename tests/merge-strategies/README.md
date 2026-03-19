# Merge Strategy Benchmark

Reproducible tests for evaluating git merge conflict resolution strategies
in the set-core orchestration context.

## Why This Exists

In E2E runs #13–#17, merge conflicts were the #1 cause of sentinel interventions.
Root causes and frequency:

| Conflict Type | Runs Affected | Frequency | Manual Interventions |
|---|---|---|---|
| `pnpm-lock.yaml` only | #3,#8,#13,#14,#15,#16 | Every run | 1–3/run |
| `.claude/*` runtime files | #13,#16,#17 | Most runs | 1–3/run |
| `package.json` additive | #15 (2 changes) | Occasional | 1/run |
| App code semantic | #13 | Rare | 0–1/run |
| Mixed (lockfile+app) | #16,#17 | Every run | 3–5/run |

**Mixed conflicts were the hardest** — the partial_mode=false bug meant lockfiles
were never auto-resolved when app code also conflicted, forcing LLM to process
10K-line pnpm-lock.yaml (which always failed).

## Strategies Tested

| Strategy | File | Status |
|---|---|---|
| S1: partial_mode=true (P0 fix) | `strategy-1-partial-mode.sh` | ✅ committed `8144b8d4f` |
| S2: `.gitattributes` merge=ours | `strategy-2-gitattributes.sh` | 🧪 testing |
| S3: post-merge hook regeneration | `strategy-3-post-merge-hook.sh` | 🧪 testing |
| S4: `@pnpm/merge-driver` | `strategy-4-pnpm-driver.sh` | 🧪 testing |
| S5: Engine serialization (P2) | `strategy-5-engine-serialize.md` | 📋 planned |

## Benchmark Scenarios

Each strategy is tested against these canonical conflict scenarios:

| ID | Scenario | Expected Behavior |
|---|---|---|
| SC1 | Lockfile-only conflict | Auto-resolved, no LLM needed |
| SC2 | Mixed: lockfile + app code | Lockfile auto, app code → LLM |
| SC3 | `.claude/*` runtime + lockfile | Both auto-resolved |
| SC4 | `package.json` additive deps | jq deep-merge |
| SC5 | App code only (semantic) | LLM or agent-rebase |
| SC6 | `prisma/schema.prisma` conflict | Agent-rebase (no auto-resolve) |

## Running the Benchmark

```bash
cd /home/tg/code2/set-core
./tests/merge-strategies/run-benchmark.sh /tmp/minishop-run3
```

Output: `tests/merge-strategies/results/YYYY-MM-DD-HH-MM.md`

## Metrics Captured

For each strategy × scenario:
- **conflict_appeared**: did git produce conflict markers?
- **auto_resolved**: resolved without human/LLM?
- **llm_input_lines**: lines passed to LLM (0 = ideal)
- **lockfile_valid**: lockfile consistent after resolution?
- **time_seconds**: wall clock time
- **requires_git_config**: needs `git config` outside repo?
- **requires_install**: needs global tool install?

## Results Summary

Results are written to `results/` after each benchmark run.
See latest: `results/latest.md` (symlink).

## Integration Plan

Based on benchmark results, winning strategies get integrated into:
1. `bin/set-merge` — merge conflict resolution pipeline
2. `tests/e2e/run.sh` — scaffold setup (gitattributes, hooks)
3. `lib/set_orch/dispatcher.py` — bootstrap_worktree() post-merge hooks
4. `set-project init` (set-project-base) — project-level gitattributes
