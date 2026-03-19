# Tasks: permanent-e2e-directory

## run.sh — default BASE_DIR
- [x] Change `BASE_DIR="${TMPDIR:-/tmp}"` to use `~/.local/share/set-core/e2e-runs/` with `WT_E2E_DIR` override
- [x] Update usage comment (line 7) with new default path
- [x] Update `--project-dir` comment to say "Override base dir" instead of "Persistent"

## run-complex.sh — default BASE_DIR
- [x] Same BASE_DIR change as run.sh
- [x] Update usage comment (line 9) with new default path
- [x] Update `--project-dir` comment

## README.md — example paths
- [x] Update all `/tmp/minishop-e2e` references to new default path
- [x] Update cleanup section with new paths

## E2E-GUIDE.md — example paths and patterns
- [x] Update worktree sync example (lines 58-59) to use `git worktree list` pattern instead of hardcoded `/tmp/` glob
- [x] Update Launch section (lines 239-240) default path comments
- [x] Update Parallel Runs section (line 289) path examples

## merge-strategies/run-benchmark.sh
- [x] Update default PROJECT path (line 5, 15) from `/tmp/minishop-run3` to new default location
