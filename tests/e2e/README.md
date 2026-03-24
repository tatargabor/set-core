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
4. Generates `set/orchestration/config.yaml` with env_vars, discord, gate config
5. Starts the sentinel (or prints instructions)

## What the Pipeline Does

```
Sentinel start
  → Digest generation (spec → structured requirements/domains)
  → Decompose (requirements → change plan with dependencies)
  → Dispatch agents (parallel worktrees, max_parallel from config)
      → Agent: ff (create artifacts) → apply (implement tasks)
      → Verify gates: build → test → e2e → lint → review → rules
      → If gate fails: retry with context (screenshot paths, review findings)
  → Merge queue (integrate main → branch → ff-only merge)
      → Integration gates: build + test + e2e (warn-only)
  → Next change dispatched
```

## Key Config Options (config.yaml)

| Key | Description |
|-----|-------------|
| `env_vars` | Key-value pairs written to `.env` in every worktree (e.g., `DATABASE_URL`) |
| `e2e_command` | Playwright command — auto-detected from profile if not set |
| `e2e_timeout` | Seconds before e2e gate times out |
| `review_before_merge` | Run LLM code review gate (default: true) |
| `discord.channel_name` | Discord notifications channel |

## Sentinel Flags

| Flag | Description |
|------|-------------|
| `--spec <path>` | Spec file or directory for digest |
| `--fresh` | Force fresh start (re-plan from scratch) |
| `--auto-approve-reset` | Skip approval gate on spec hash change (for CI) |

Without `--auto-approve-reset`, the sentinel will pause and wait for approval before resetting orchestration state when it detects a spec change. Create `.set/.sentinel-approve-reset` to approve.

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
│   ├── craftbrew/           ← Run 1-9 reports
│   └── craftbrew-findings.md
└── assets/                  ← Screenshots and test utilities
    ├── screenshots/
    └── capture-screenshots.ts
```

## Active Runs

| Run | Status | Started | Bugs Found |
|-----|--------|---------|------------|
| **craftbrew-run9** | **running** | 2026-03-22 | Bug #33 (stall detection done check), Bug #34 (REVIEW PASS false positive), Bug #35 (max-iter done check) |

## Run Logs

Run logs live in `runs/<project>/run-N.md` and document bugs found, metrics, and conclusions. They're the primary feedback loop for set-core development.

## Cleanup

```bash
# Kill running agents and sentinel
pkill -f "set-sentinel.*<name>" 2>/dev/null || true
pkill -f "set-loop.*<name>" 2>/dev/null || true

# Remove worktrees
cd ~/.local/share/set-core/e2e-runs/<name>-runN
git worktree list --porcelain | grep "^worktree " | awk '{print $2}' | \
  xargs -I{} git worktree remove {} --force 2>/dev/null || true

# Remove project
rm -rf ~/.local/share/set-core/e2e-runs/<name>-runN
rm -rf ~/.local/share/set-core/memory/<name>-runN
set-project remove <name>-runN 2>/dev/null || true
```
