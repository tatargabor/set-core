# Proposal: sentinel-e2e-intelligence

## Why

The sentinel skill (`.claude/commands/wt/sentinel.md`) and the E2E guide (`tests/e2e/E2E-GUIDE.md`) have diverged. The E2E guide contains hard-won operational knowledge from 20+ orchestration runs that isn't reflected in the sentinel's decision logic. Meanwhile, the sentinel's guardrails are too restrictive for E2E use (can't fix framework bugs) and too permissive in dangerous areas (state reset accessible without safety rails).

Specific gaps:
- **No expected-pattern awareness**: sentinel can't distinguish "Prisma generate needed post-merge" from a real build failure
- **No token-budget stuck detection**: a change burning >500K tokens with no commits goes unnoticed
- **No dependency deadlock recognition**: dependent changes stuck in `pending` forever when a dependency fails
- **No framework fix authority for E2E**: sentinel must stop and report instead of fixing obvious wt-tools bugs mid-run
- **Unsafe state reset**: full state reset (destructive) is documented inline with no safety guardrails

## What Changes

- **A: Expected patterns → Tier 1 expansion** — add known false-positive patterns (post-merge Prisma generate, watchdog grace period for new dispatches, stale `.next/` cache) to the sentinel's Tier 1 (defer) list with explanations
- **B: Token stuck detection** — sentinel warns when a change exceeds token budget threshold with no recent commits; included in completion report
- **C: Dependency deadlock detection** — sentinel recognizes when pending changes are blocked by failed dependencies and warns/reports instead of silently waiting
- **D: E2E framework fix authority (Tier 3)** — new tier allowing sentinel to fix wt-tools framework code and deploy to running test, with strict scope boundary: wt-tools repo only, consumer project code NEVER, no branch merging, no quality decisions
- **E: State reset → dedicated CLI tool** — remove state reset guidance from sentinel scope, create `wt-orchestrate reset` with `--partial` (safe default, failed→pending) and `--full` (requires `--yes-i-know` flag)

## Capabilities

### New Capabilities
- `sentinel-e2e-mode` — E2E-specific sentinel mode with Tier 3 framework fix authority and operational intelligence from E2E runs
- `orchestrate-reset-cli` — dedicated CLI tool for safe orchestration state reset with partial/full modes

### Modified Capabilities
- `sentinel-supervisor` (existing) — expanded Tier 1 list, token stuck detection, dependency deadlock warnings

## Impact

- **Files**: `.claude/commands/wt/sentinel.md`, `docs/sentinel.md`, `bin/wt-orchestrate`, `tests/e2e/E2E-GUIDE.md`
- **Risk**: Low-medium — sentinel behavior changes are additive (new warnings, expanded tier list). E2E mode is opt-in. Reset CLI is new tool.
- **Testing**: Run against next E2E orchestration to validate false-positive reduction and stuck detection
