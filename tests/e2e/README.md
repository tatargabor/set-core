# E2E Tests

End-to-end tests for set-core orchestration. Each scaffold is a spec — agents build the entire project from it.

## Scaffolds

| Scaffold | Complexity | Pages | Purpose |
|----------|-----------|-------|---------|
| **micro-web** | Minimal | 5 | Quick gate enforcement validation (~30min) |
| **minishop** | Medium | ~15 | Standard pipeline test — cart, checkout, admin |
| **craftbrew** | Complex | ~30 | Full-scale stress test — 15+ changes, multi-phase |

## Prerequisites

```bash
command -v set-project    # set-core project manager
command -v set-sentinel   # set-core orchestration sentinel
set-project list-types    # should show "web (built-in)"
```

## Quick Start

```bash
# Micro-web — fastest, validates new gate enforcement
./tests/e2e/runners/run-micro-web.sh

# MiniShop — standard pipeline test
./tests/e2e/runners/run-minishop.sh

# CraftBrew — full stress test (needs design snapshot)
./tests/e2e/runners/run-craftbrew.sh
```

Each runner:
1. Creates a project at `~/.local/share/set-core/e2e-runs/<name>-runN/`
2. Copies the spec from `scaffolds/<name>/docs/`
3. Runs `set-project init --project-type web --template nextjs`
4. Starts the sentinel

## Directory Structure

```
tests/e2e/
├── scaffolds/               ← Spec files (input for orchestration)
│   ├── minishop/docs/       ← 6-product webshop spec
│   ├── craftbrew/docs/      ← Specialty coffee webshop spec
│   └── micro-web/docs/      ← Minimal 5-page app spec
├── runners/                 ← Launch scripts
│   ├── run-minishop.sh
│   ├── run-craftbrew.sh
│   └── run-micro-web.sh
├── runs/                    ← Run logs and findings
│   ├── minishop/            ← Run 13-19 reports
│   ├── craftbrew/           ← Run 1-7 reports
│   └── craftbrew-findings.md
└── assets/                  ← Screenshots and test utilities
    ├── screenshots/
    └── capture-screenshots.ts
```

## Run Logs

Run logs live in `runs/<project>/run-N.md` and document bugs found, metrics, and conclusions. They're the primary feedback loop for set-core development.

## Cleanup

```bash
# Kill running agents
pkill -f "set-sentinel.*<name>" 2>/dev/null || true

# Remove project
rm -rf ~/.local/share/set-core/e2e-runs/<name>-runN
set-project remove <name>-runN 2>/dev/null || true
```
