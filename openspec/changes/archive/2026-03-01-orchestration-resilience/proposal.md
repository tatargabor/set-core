## Why

The v5/v6 orchestration runs on sales-raketa revealed several failure modes that cause token waste and stuck pipelines. The most critical: when `opsx:ff` fails to create `tasks.md`, the Ralph loop enters an infinite cycle — re-running `ff:` every iteration with no escape, burning 150K+ tokens on what should be a trivial change. Secondary issues include missing `.env` in worktrees, memory pollution from redundant loop iterations, and no token budget guardrails.

## What Changes

- **Ralph loop idle detection**: If N consecutive iterations produce no git diff and no new commits, auto-stop and mark the change as stale (not done)
- **Post-ff artifact validation**: After running `opsx:ff`, verify `tasks.md` exists. If missing after 2 attempts, escalate (checkpoint) instead of infinite retry
- **Fallback done criteria**: When `done_criteria: openspec` and tasks.md is missing but proposal+design exist and there are commits with clean working tree, treat as "done" with warning
- **Worktree .env bootstrap**: Copy `.env` (and `.env.local`) from main repo to new worktrees in `wt-new`
- **Loop iteration token budget**: Track cumulative token usage per change; checkpoint when budget exceeded (S: 100K, M: 300K, L: 500K)
- **Memory dedup guard in loops**: Skip session-end memory save when Ralph loop iteration produced no meaningful work (no commits, no file changes)

## Capabilities

### New Capabilities
- `loop-idle-detection`: Detect and handle Ralph loop iterations that produce no useful work — max idle iterations, auto-stop, stale marking
- `loop-token-budget`: Track and enforce per-change token budgets based on change size — checkpoint on exceed

### Modified Capabilities
- `ralph-loop`: Add post-ff validation, fallback done criteria when tasks.md missing
- `worktree-tools`: Copy .env/.env.local from main repo during worktree bootstrap
- `memory-dedup`: Skip memory save for no-op loop iterations

## Impact

- `bin/wt-loop` — main changes: idle detection, post-ff validation, fallback done, token budget
- `bin/wt-new` — .env copy in bootstrap_dependencies
- `bin/wt-orchestrate` — token budget tracking per change in state
- Session-end hooks — conditional save based on loop iteration productivity
