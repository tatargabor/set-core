# MiniShop E2E Test

End-to-end test for set-core orchestration. A single spec file (`scaffold/docs/v1-minishop.md`) is the only input — agents build an entire Next.js webshop from it.

## Prerequisites

```bash
# These must be installed and in PATH:
command -v pnpm          # pnpm package manager
command -v set-project    # set-core project manager
command -v set-sentinel   # set-core orchestration sentinel

# set-project-web plugin must be registered:
set-project list-types    # should show "web"

# If not installed:
pip install -e /path/to/set-project-web
```

## Run

```bash
# Step 1: Initialize test project (creates dir, copies spec, runs set-project init)
./tests/e2e/run.sh                    # default: ~/.local/share/set-core/e2e-runs/minishop-runN
./tests/e2e/run.sh ~/e2e-test         # or custom dir

# Step 2: Start orchestration
cd ~/.local/share/set-core/e2e-runs/minishop-runN  # or your custom dir
set-sentinel --spec docs/v1-minishop.md
```

The sentinel will:
- Plan changes from the spec (the planner may add a bootstrap change before the 6 feature changes)
- Dispatch agents in parallel (max 2)
- Manage merges, smoke tests, and checkpoints

## Re-run (clean slate)

To wipe a previous run and start fresh:

```bash
# 1. Kill any running agents/sentinels
pkill -f "set-sentinel.*minishop" 2>/dev/null || true
pkill -f "claude.*minishop" 2>/dev/null || true

# 2. Remove old project + memory
rm -rf ~/.local/share/set-core/e2e-runs/minishop-runN
rm -rf ~/.local/share/set-core/memory/minishop-runN
set-project remove minishop-runN 2>/dev/null || true

# 3. Re-initialize and run
./tests/e2e/run.sh
cd ~/.local/share/set-core/e2e-runs/minishop-runN
set-sentinel --spec docs/v1-minishop.md
```

## After Completion

```bash
cd ~/.local/share/set-core/e2e-runs/minishop-runN

# Step 3: Generate benchmark report
set-e2e-report --project-dir .

# Step 4 (optional): Update set-core README benchmark section
set-e2e-report --project-dir . --update-readme /path/to/set-core/README.md
```

The report generator extracts all data from `orchestration-state.json` and `.claude/orchestration.log`:

| Output | Contents |
|---|---|
| `e2e-report.md` | Full benchmark: summary, Gantt chart, quality gates, retries, test counts |
| `e2e-screenshots/` | Playwright screenshots of each page (optional) |
| `e2e-report-prev.md` | Previous report (rotated automatically) |

### What the report includes

- **Summary table** — wall clock, tokens, changes merged/failed, test counts
- **Gantt chart** — ASCII timeline showing parallel agent execution with overlap detection
- **Per-change results** — status, tokens, duration, retries per change
- **Quality gate breakdown** — Jest/Build/E2E/Smoke result per change, retry causes
- **Test coverage** — Jest suite list + Playwright spec list
- **Token breakdown** — input/output/cache per change (when token tracking is active)
- **Run comparison** — diff table against previous report (if rotated)

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
rm -rf ~/.local/share/set-core/e2e-runs/minishop-runN
rm -rf ~/.local/share/set-core/memory/minishop-runN
set-project remove minishop-runN
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `set-project-web plugin not installed` | `pip install -e /path/to/set-project-web` |
| `run.sh` says existing project detected | Delete the test dir or use a different path |
| Agent can't find spec | Check `docs/v1-minishop.md` exists in the test project |
| Port 3000 in use | Kill existing process: `lsof -ti:3000 \| xargs kill` |
| Sentinel stuck | Check `set-sentinel` logs, use `set-status` to see agent states |
