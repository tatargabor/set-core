# Proposal: permanent-e2e-directory

## Problem

E2E test projects (minishop, craftbrew) are created in `/tmp/` by default. This is ephemeral — the OS can delete them on reboot or via `tmpfiles.d` cleanup. Lost runs mean lost git history, worktrees, and orchestration state.

## Solution

Change the default base directory from `/tmp/` to `~/.local/share/set-core/e2e-runs/` (XDG data directory, alongside the existing memory storage). Add `WT_E2E_DIR` env var for override.

## Scope

- `tests/e2e/run.sh` — default BASE_DIR
- `tests/e2e/run-complex.sh` — default BASE_DIR
- `tests/e2e/README.md` — example paths
- `tests/e2e/E2E-GUIDE.md` — example paths, worktree sync examples
- `tests/merge-strategies/run-benchmark.sh` — default project path

Historical run logs (run-*.md) are NOT modified — they document past runs accurately.
