---
name: e2e-runs
description: How to set up, start, compare and harvest end-to-end orchestration runs, and how to run the web dashboard's Playwright suite. Use when starting or supervising an E2E run, when reading a run log for framework bugs, when comparing two runs, or when the dashboard UI changed and its Playwright tests need running.
---

# E2E runs, run diagnostics, and the dashboard's Playwright suite

> Moved out of `CLAUDE.md` on 2026-08-22 so it loads when it is needed rather than in
> every session. Nothing was cut — the text below is those three sections verbatim.

## Consumer Project Diagnostics

set-core is developed and battle-tested through consumer projects. Before fixing bugs or adding features, always consult the primary consumer for real-world diagnostics.

### Harvest (primary tool)

After every E2E run, use `set-harvest` to scan consumer projects for framework-relevant fixes:
```bash
set-harvest                          # scan all registered consumer projects
set-harvest --project craftbrew-run-20260320-1445 # scan single project
set-harvest --dry-run                # preview without updating state
```

The harvest tool scans ISS fix commits, classifies them (framework-relevant vs project-specific), and presents them for interactive adoption into planning rules, templates, or core code.

### Manual workflow

1. **Read the latest orchestration run log** — each log has a "set-core Bugs to Report" section and "Conclusions for set-core Development" with prioritized issues, root cause analysis, and design decisions.
2. **Diff .claude/ for upstream changes** — during orchestration, the sentinel or user may improve commands, skills, or configs in the consumer's `.claude/`. Diff against set-core source to find changes to adopt.
3. **Check orchestration.yaml** — the consumer's config reflects production usage. Understand what directives are actually used before changing defaults.
4. **Use run comparison data** — run logs contain quantitative comparisons (wasted iterations, token efficiency, intervention count). Use these to validate whether a fix actually improved things.

### Bidirectional flow

```
set-core (source)                     consumer project
   │                                      │
   ├── set-project init ──────────────────►│  deploy .claude/ files
   │                                      │
   │◄── run logs (bugs, design) ──────────┤  diagnostics after each run
   │◄── .claude/ diffs ──────────────────┤  sentinel/user improvements
   │◄── orchestration.yaml ──────────────┤  config evolution
   │                                      │
   ├── fix bugs, add features             │
   ├── set-project init ──────────────────►│  redeploy
```

## E2E Run Setup

**Read `tests/e2e/README.md` first** — it documents scaffolds, fallback logic, and runner internals.

**NEVER** initialize E2E runs manually. Always use `tests/e2e/runners/`:
```bash
./tests/e2e/runners/run-micro-web.sh     # scaffold + init + register
./tests/e2e/runners/run-minishop.sh      # scaffold + init + register
./tests/e2e/runners/run-craftbrew.sh     # scaffold + init + register
```

If you MUST init manually, **always** include `--project-type web --template nextjs`:
```bash
set-project init --name minishop-run-YYYYMMDD-HHMM --project-type web --template nextjs
```
Without `--project-type web`, no `project-type.yaml` is created → NullProfile loads → integration gates silently skip (no build/test/e2e detection).

### Starting the sentinel

After the runner script finishes, start the sentinel via the **manager API** (not CLI):
```bash
# Restart set-web first if the project was just registered (picks up new projects)
systemctl --user restart set-web && sleep 5

# Start sentinel via API
curl -X POST http://localhost:7400/api/<project>/sentinel/start \
  -H 'Content-Type: application/json' -d '{"spec":"docs/spec.md"}'
```

**NEVER** use `nohup set-sentinel` from CLI — that only starts the orchestrator without the sentinel poll loop.

### Comparing runs for divergence

After two runs of the same spec, compare their structural similarity:
```bash
./bin/set-compare minishop-run-20260315-0930 minishop-run-20260318-1415          # markdown report
./bin/set-compare micro-web-run-20260322-1100 micro-web-run-20260325-0845 --json # JSON output
./bin/set-compare run-a run-b --output docs/comparison.md # save to file
```

Metrics: route coverage, schema equivalence, dependencies, functional categories, template compliance, convention compliance, E2E test results. Score 0-100 with verdict.

## Web Dashboard E2E Tests

The web dashboard (`web/`) has Playwright E2E tests that verify the UI renders API data correctly. Tests run against a **live server** with a **real project** — no mocks.

### Running

```bash
cd web/

# Prerequisites: set-orch-core running, project with completed orchestration
E2E_PROJECT=minishop-run-20260315-0930 pnpm test:e2e

# View HTML report (screenshots on failure, step-by-step trace)
pnpm test:e2e:report

# Single test file
E2E_PROJECT=minishop-run-20260315-0930 npx playwright test changes-data

# Debug with visible browser
E2E_PROJECT=minishop-run-20260315-0930 npx playwright test --headed
```

### What they test

Gate icons, token values, status colors, session counts, duration calculation, phase grouping, chart rendering, log display, tab navigation, action buttons — every tab of the dashboard. Tests fetch API data first, then assert the UI matches. See `web/tests/e2e/README.md` for details.

### After refactoring the web UI

Always run the E2E suite to verify nothing broke. The HTML report (`pnpm test:e2e:report`) shows exactly which assertions failed with screenshots.
