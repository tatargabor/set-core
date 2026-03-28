[< Back to Index](../INDEX.md)

# First Project Setup

Get set-core running on your own project in 10 minutes.

## Prerequisites

| Requirement | Version | Check |
|-------------|---------|-------|
| Python | 3.10+ | `python3 --version` |
| Git | 2.30+ | `git --version` |
| Node.js | 18+ | `node --version` |
| Claude Code | Latest | `claude --version` |
| jq | Any | `jq --version` |

## Step 1: Install set-core

```bash
git clone https://github.com/tatargabor/set-core.git
cd set-core && ./install.sh
```

The installer adds `set-*` commands to `~/.local/bin/` and installs the Python package.

## Step 2: Initialize your project

```bash
cd ~/your-project
set-project init --project-type web --template nextjs
```

This deploys:
- `.claude/` directory with rules, skills, and commands
- `orchestration.yaml` configuration
- `project-type.yaml` for the web profile

> **Important:** Always include `--project-type web` for web projects. Without it, NullProfile loads and integration gates silently skip.

## Step 3: Write a spec

Create a markdown file describing what you want to build. A spec should include:
- **Overview** — what the application does
- **Domains** — functional areas (auth, products, cart, etc.)
- **Requirements** — specific features with acceptance criteria
- **Tech stack** — framework, database, deployment constraints

See the [OpenSpec guide](../guide/openspec.md) for spec writing best practices.

## Step 4: Run orchestration

Open a Claude Code session in your project:

```bash
# In Claude Code:
/set:sentinel --spec docs/my-spec.md --max-parallel 2
```

Or use the run script for a fully automated setup:

```bash
./tests/e2e/run.sh your-project
```

## Step 5: Monitor

- **Dashboard:** `http://localhost:7400` — real-time orchestration state
- **CLI:** `set-status` — JSON status output
- **Worktrees:** `set-list` — see active parallel branches

The manager landing page shows all registered projects:

![Manager project list](../images/auto/web/manager-project-list.png)

Click a project to open the orchestration dashboard:

![Dashboard overview](../images/auto/web/dashboard-overview.png)

From the CLI, `set-list` shows active worktrees:

![set-list output](../images/auto/cli/set-list.png)

Run `set-audit scan` to check project health:

![set-audit scan output](../images/auto/cli/set-audit-scan.png)

## What to Expect

- The sentinel digests your spec, decomposes it into changes, and dispatches agents
- Each agent works in an isolated git worktree
- Quality gates (test, build, E2E, code review) run before each merge
- The sentinel auto-replans if spec coverage is incomplete

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Gates silently skip | Check `project-type.yaml` exists — re-run `set-project init --project-type web` |
| Agent crashes | Sentinel auto-restarts — check dashboard for details |
| Build failures after merge | Integration gates should catch this — check gate logs |
| No worktrees created | Verify spec was digested — check `orchestration-state.json` |

See the [quick start guide](../guide/quick-start.md) for more detail.

<!-- specs: documentation-system, first-project-setup, orchestration-engine -->
