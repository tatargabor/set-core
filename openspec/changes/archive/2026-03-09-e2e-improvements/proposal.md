## Why

E2E #3 validated watchdog and checkpoint fixes but revealed:
1. **Token counting inflated** — `wt-usage --since` scans ALL `~/.claude/projects/` dirs, not just the current worktree. Parallel changes + user sessions get cross-counted.
2. **No E2E report** — no structured summary with screenshots after a run completes.
3. **Minishop is API-only Express** — doesn't test the `set-project-web` stack (Next.js, shadcn/ui, Tailwind, Prisma). A realistic frontend + modern stack will expose real set-core bugs when agents work with complex frameworks.

## What Changes

1. **Token scoping** — add `--project-dir` filter to `wt-usage` and `UsageCalculator` so token counting is per-worktree.
2. **E2E report with screenshots** — generate markdown report after orchestration, capture Playwright screenshots of the running app.
3. **Minishop scaffold rewrite → Next.js** — replace Express+SQLite scaffold with Next.js App Router + Prisma + SQLite + shadcn/ui + Tailwind. This also validates `set-project-web` conventions. More complex feature set (6 changes instead of 4) to stress-test parallel orchestration, merge conflicts, and cross-cutting concerns.

## Capabilities

### New Capabilities
- `e2e-report`: Post-run report generation with stats, timeline, and Playwright screenshots
- `minishop-nextjs`: Next.js scaffold with Prisma, shadcn/ui, Tailwind for E2E testing

### Modified Capabilities
- `orchestration-token-tracking`: Add project-scoped filtering to token counting

## Impact

- `bin/wt-usage` — add `--project-dir` CLI flag
- `gui/usage_calculator.py` — add optional `project_dir` filter
- `lib/loop/state.sh` — pass worktree project dir to `get_current_tokens()`
- `tests/e2e/scaffold/` — complete rewrite: Next.js App Router + Prisma + shadcn/ui + Tailwind
- `tests/e2e/scaffold/docs/v1-minishop.md` — new feature roadmap with 6 changes
- `tests/e2e/run.sh` — update for pnpm, Prisma, and report generation
- New: `bin/wt-e2e-report` — report generator with Playwright screenshot capture
