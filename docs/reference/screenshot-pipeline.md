[< Back to Index](../INDEX.md)

# Screenshot Pipeline

Automated screenshot generation for documentation. All screenshots are regenerated from live data — no manual capture needed.

## Quick Start

```bash
make screenshots          # regenerate everything
make screenshots-web      # dashboard only
make screenshots-cli      # CLI output only
make screenshots-app      # consumer app only
```

## Dependencies

| Tool | Install | Required for |
|------|---------|-------------|
| **Playwright + Chromium** | `cd web && pnpm install` | Web dashboard + consumer app screenshots |
| **ansi2html** | `pip install ansi2html` | CLI output screenshots |
| **set-core tools** | `pip install -e .` (from set-core root) | CLI commands (`set-list`, `set-status`, etc.) |
| **Running set-web** | `set-orch-core serve --port 7400` | Web dashboard screenshots |

## Output Structure

```
docs/images/auto/
├── web/                          # Web dashboard screenshots
│   ├── manager-project-list.png  # Landing page with all projects
│   ├── dashboard-overview.png    # Orchestration dashboard header
│   ├── tab-changes.png           # Changes tab (gate badges, tokens)
│   ├── tab-phases.png            # Phases tab (dependency tree)
│   ├── tab-tokens.png            # Token usage chart
│   ├── tab-sessions.png          # Agent session list
│   ├── tab-log.png               # Orchestration log
│   ├── tab-learnings.png         # Reflections + gate stats
│   ├── tab-agent.png             # Agent chat interface
│   ├── tab-sentinel.png          # Sentinel log
│   ├── tab-plan.png              # Plan viewer (conditional — only generated when data exists)
│   ├── tab-digest.png            # Spec digest (if data exists)
│   ├── tab-context.png           # Context analysis (conditional — needs LLM call data)
│   ├── tab-audit.png             # Audit results (conditional — only generated when data exists)
│   ├── global-issues.png         # Global issues browser
│   ├── page-memory.png           # Memory stats page
│   ├── page-settings.png         # Project settings
│   ├── page-issues.png           # Project issues
│   └── page-worktrees.png        # Worktree management
├── cli/                          # CLI terminal screenshots
│   ├── set-list.png              # Worktree listing
│   ├── set-status.png            # Orchestration status
│   ├── openspec-status.png       # OpenSpec changes (conditional — only generated when data exists)
│   ├── set-memory-stats.png      # Memory statistics
│   └── set-audit-scan.png        # Project health audit
└── app/                          # Consumer app screenshots
    ├── home.png                  # App homepage
    ├── products.png              # Product listing
    ├── product-detail.png        # Product detail page
    ├── cart.png                  # Shopping cart
    ├── admin-login.png           # Admin login form
    ├── admin.png                 # Admin dashboard
    └── admin-products-new.png    # Admin product creation
```

## Web Dashboard Screenshots

**Script:** `web/tests/e2e/screenshots.spec.ts`
**Command:** `cd web && E2E_PROJECT=minishop-run-20260312-1630 pnpm screenshot:docs`

Captures all dashboard pages via Playwright. Tabs without data for the selected project are automatically skipped.

### Project selection

- Set `E2E_PROJECT` explicitly: `E2E_PROJECT=minishop-run-20260315-0930 pnpm screenshot:docs`
- Or use `make screenshots-web` which auto-detects the latest "done" project from the API

### Requirements

- set-web running on port 7400 (`set-orch-core serve`)
- At least one registered project with completed orchestration

## CLI Screenshots

**Script:** `scripts/capture-cli-screenshots.py`
**Command:** `python3 scripts/capture-cli-screenshots.py`

Runs CLI commands, captures ANSI output, renders through ansi2html into a styled dark terminal window (Catppuccin Mocha theme), then screenshots via Playwright.

### Adding new CLI commands

Edit `COMMANDS` list in `scripts/capture-cli-screenshots.py`:

```python
COMMANDS = [
    ("output-filename", "shell-command", "Description"),
    ...
]
```

### Single command

```bash
python3 scripts/capture-cli-screenshots.py set-list
```

## Consumer App Screenshots

**Script:** `scripts/capture-app-screenshots.sh` + `web/tests/e2e/app-screenshots.spec.ts`
**Command:** `./scripts/capture-app-screenshots.sh [project-name-or-path]`

Starts a dev server for a consumer project, auto-discovers Next.js routes from `src/app/`, captures full-page screenshots via Playwright, then stops the server.

### Project selection

```bash
./scripts/capture-app-screenshots.sh                    # latest "done" E2E run
./scripts/capture-app-screenshots.sh minishop-run-20260315-0930     # specific run name
./scripts/capture-app-screenshots.sh /path/to/project   # absolute path
```

### What it does

1. Resolves project directory (auto-detect or explicit)
2. Runs Prisma setup if applicable (generate + db push + seed)
3. Installs dependencies if needed
4. Starts `pnpm dev` on port 3100
5. Auto-discovers routes from `src/app/` (falls back to hardcoded routes)
6. Captures screenshots via Playwright
7. Stops dev server

### Route auto-discovery

The script scans `src/app/` for `page.tsx` files and builds a route list:
- Route groups `(shop)` are flattened
- Dynamic routes `[id]` are skipped (no seed data to navigate to)
- Admin pages are auto-detected and login is handled
- If no `src/app/` exists, falls back to known minishop routes

## Referencing Screenshots in Docs

Use relative paths from the doc file's location. Since most docs live in subdirectories of `docs/` (e.g., `docs/guide/`, `docs/examples/`), paths typically start with `../images/auto/`:

```markdown
<!-- From docs/guide/*.md or docs/examples/*.md -->
![Description](../images/auto/web/tab-changes.png)
![CLI output](../images/auto/cli/set-list.png)
![App page](../images/auto/app/products.png)
```

> **Note:** Paths are relative to the doc file's location, not to the `docs/` root. A file in `docs/reference/` uses `../images/auto/...`, while a file in `docs/` itself would use `images/auto/...`. Always verify with your file's depth.

## Troubleshooting

### "No done project found"

Ensure at least one registered project has `status: done` with merged changes. Check: `curl http://localhost:7400/api/projects`

### CLI screenshots empty

Ensure set-core tools are in PATH: `which set-list set-status openspec`

### Consumer app screenshots fail

- Check the project has `node_modules/` or run `pnpm install` first
- For Prisma projects, ensure SQLite is available
- Check if port 3100 is free: `ss -tlnp | grep 3100`

### ansi2html not installed

```bash
pip install ansi2html
```

<!-- specs: docs-screenshot-pipeline -->
