# MiniShop E2E Test

End-to-end test for wt-tools orchestration. A single spec file (`scaffold/docs/v1-minishop.md`) is the only input — agents build an entire Next.js webshop from it.

## Prerequisites

```bash
# These must be installed and in PATH:
command -v pnpm          # pnpm package manager
command -v wt-project    # wt-tools project manager
command -v wt-sentinel   # wt-tools orchestration sentinel

# wt-project-web plugin must be registered:
wt-project list-types    # should show "web"

# If not installed:
pip install -e /path/to/wt-project-web
```

## Run

```bash
# Step 1: Initialize test project (creates dir, copies spec, runs wt-project init)
./tests/e2e/run.sh                    # default: /tmp/minishop-e2e
./tests/e2e/run.sh ~/e2e-test         # or custom dir

# Step 2: Start orchestration
cd /tmp/minishop-e2e                  # or your custom dir
wt-sentinel --spec docs/v1-minishop.md
```

The sentinel will:
- Plan changes from the spec (the planner may add a bootstrap change before the 6 feature changes)
- Dispatch agents in parallel (max 2)
- Manage merges, smoke tests, and checkpoints

## Re-run (clean slate)

To wipe a previous run and start fresh:

```bash
# 1. Kill any running agents/sentinels
pkill -f "wt-sentinel.*minishop" 2>/dev/null || true
pkill -f "claude.*minishop" 2>/dev/null || true

# 2. Remove old project + memory
rm -rf /tmp/minishop-e2e
rm -rf ~/.local/share/wt-tools/memory/minishop-e2e
wt-project remove minishop-e2e 2>/dev/null || true

# 3. Re-initialize and run
./tests/e2e/run.sh
cd /tmp/minishop-e2e
wt-sentinel --spec docs/v1-minishop.md
```

## After Completion

```bash
# Generate E2E report with screenshots
cd /tmp/minishop-e2e
wt-e2e-report --project-dir .

# Report output:
# - e2e-report.md        (summary, per-change stats, timeline)
# - e2e-screenshots/     (Playwright screenshots of each page)
```

## Verification

Check `e2e-report.md` and the verification checklist at the end of `docs/v1-minishop.md`. Key items:

- All changes completed
- `pnpm test` passes
- `pnpm build` succeeds
- Products page shows 6 products with EUR prices
- Cart + checkout flow works
- Admin auth protects only `/admin/*` routes
- Screenshots captured for all main pages

## Cleanup

```bash
rm -rf /tmp/minishop-e2e
rm -rf ~/.local/share/wt-tools/memory/minishop-e2e
wt-project remove minishop-e2e
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `wt-project-web plugin not installed` | `pip install -e /path/to/wt-project-web` |
| `run.sh` says existing project detected | Delete the test dir or use a different path |
| Agent can't find spec | Check `docs/v1-minishop.md` exists in the test project |
| Port 3000 in use | Kill existing process: `lsof -ti:3000 \| xargs kill` |
| Sentinel stuck | Check `wt-sentinel` logs, use `wt-status` to see agent states |
