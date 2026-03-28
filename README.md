# set-core

**Autonomous multi-agent orchestration for Claude Code** — give it a spec, get merged features.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: Linux & macOS](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS-lightgrey.svg)]()

set-core takes a markdown spec, decomposes it into independent changes, dispatches parallel Claude Code agents in git worktrees, runs quality gates on each, and merges the results. You provide the spec — it builds the app.

---

## The Pipeline

```
spec.md ──► digest ──► decompose ──► parallel agents ──► verify ──► merge ──► done
```

<details>
<summary>What's actually happening under the hood</summary>

```
spec.md + design-snapshot.md (Figma)
  │
  ▼
┌───────────────────────────────────────────────────────────┐
│ Sentinel (autonomous supervisor)                          │
│  ├─ digests spec into requirements + domain summaries     │
│  ├─ decomposes into independent changes (DAG)             │
│  ├─ dispatches each to its own git worktree               │
│  ├─ monitors progress, restarts on crash                  │
│  ├─ merges verified results back to main                  │
│  └─ auto-replans until full spec coverage                 │
│                                                           │
│  Per change:                                              │
│  ┌──────────────────────────────────────────────────┐     │
│  │ Ralph Loop                                       │     │
│  │  ├─ OpenSpec artifacts (proposal → design → code) │     │
│  │  ├─ iterative implementation with tests           │     │
│  │  ├─ progress-based trend detection                │     │
│  │  └─ auto-pause on stall or budget limit           │     │
│  └──────────────────────────────────────────────────┘     │
│                                                           │
│  Quality gates (per change, before merge):                │
│  ┌──────────────────────────────────────────────────┐     │
│  │ Jest/Vitest → Build → Playwright E2E             │     │
│  │ → Code Review → Spec Coverage → Smoke Test       │     │
│  │ (gate profiles: per-change-type configuration)    │     │
│  └──────────────────────────────────────────────────┘     │
│                                                           │
│  Across all agents:                                       │
│  ┌──────────────────────────────────────────────────┐     │
│  │ Memory Layer                                     │     │
│  │  ├─ 5-layer hooks inject context per tool         │     │
│  │  ├─ agents learn from each other's work           │     │
│  │  └─ conventions survive across sessions           │     │
│  └──────────────────────────────────────────────────┘     │
└───────────────────────────────────────────────────────────┘
  │
  ▼
merged, tested, done
```

</details>

---

## See It In Action

<p align="center">
  <img src="docs/images/auto/web/dashboard-overview.png" width="48%" alt="set-core web dashboard showing orchestration status, agent progress, and quality gates" />
  &nbsp;
  <img src="docs/images/auto/app/products.png" width="48%" alt="MiniShop products page built autonomously from spec" />
</p>
<p align="center"><em>From spec to working app — autonomously.</em></p>

---

## Key Features

| | Feature | Description |
|---|---|---|
| :gear: | **Full Pipeline** | Spec to merged code — digest, decompose, dispatch, verify, merge — hands-off. [Guide](docs/guide/orchestration.md) |
| :shield: | **Quality Gates** | Test, build, E2E, code review, spec coverage, and smoke gates run before every merge. [Reference](docs/guide/quality-gates.md) |
| :brain: | **Persistent Memory** | Cross-session semantic recall — agents learn from each other and remember conventions. [Docs](docs/guide/memory.md) |
| :bar_chart: | **Web Dashboard** | Browser-based monitoring for orchestration state, agent status, tokens, and logs. [Setup](docs/guide/dashboard.md) |
| :clipboard: | **OpenSpec Workflow** | Structured artifact flow (proposal, design, spec, tasks, code) keeps agents on track. [Workflow](docs/guide/openspec.md) |
| :jigsaw: | **Plugin System** | Project-type plugins (web, custom) add domain rules, gates, and conventions. [Architecture](docs/guide/plugins.md) |

---

## Quick Start

```bash
git clone https://github.com/tatargabor/set-core.git
cd set-core && ./install.sh

cd ~/my-project
set-project init --project-type web --template nextjs

# In a Claude Code session:
/set:sentinel --spec docs/my-spec.md --max-parallel 2
```

See [docs/guide/quick-start.md](docs/guide/quick-start.md) for detailed setup, configuration, and first-run walkthrough.

---

## How It Works

The orchestration engine reads a markdown spec and produces a structured digest — domain summaries, requirement IDs, and a dependency graph. An LLM decomposes that digest into independent changes organized in a DAG with phases, injecting relevant design tokens from Figma when available.

Each change is dispatched to its own git worktree where a Ralph Loop runs Claude Code autonomously: creating OpenSpec artifacts, implementing iteratively, and tracking progress with trend detection. The sentinel supervisor monitors all agents, handles crashes, and restarts stalled work.

Before any change merges to main, it passes through configurable quality gates — unit tests, build, Playwright E2E, LLM code review, spec coverage check, and post-merge smoke test. Gate profiles adjust requirements per change type. After merge, auto-replan checks remaining spec coverage and dispatches new changes if needed.

Full architecture walkthrough: [docs/learn/how-it-works.md](docs/learn/how-it-works.md) | [docs/howitworks/](docs/howitworks/)

---

## Built & Battle-Tested

set-core is developed through continuous E2E orchestration runs against real projects.

| Metric | Value |
|--------|-------|
| Commits | 1,287 |
| Capability specs | 363 |
| Python LOC | 44,000 |
| TypeScript LOC | 12,000 |
| Benchmark: MiniShop run #4 | 6/6 changes merged, 0 human interventions, 1h 45m |
| Benchmark: MiniShop run #15 | 8/8 changes merged, Figma design bridge, gate profiles |
| Stress test: CraftBrew | 17+ spec files, i18n, subscriptions, multi-phase |

Every change passes: **Test, Build, E2E, Code Review, Spec Coverage, Merge, Post-merge Smoke.**

Full run history and findings: [docs/learn/journey.md](docs/learn/journey.md)

---

## Documentation

| Section | Contents |
|---------|----------|
| **[Guide](docs/guide/)** | Quick start, configuration, orchestration setup, dashboard, memory |
| **[Reference](docs/reference/)** | CLI tools, MCP server, gate profiles, orchestration.yaml schema |
| **[Learn](docs/learn/)** | How it works, architecture deep-dives, journey and benchmarks |
| **[Examples](docs/examples/)** | MiniShop walkthrough, CraftBrew stress test, plugin creation |
| **[How It Works (chapters)](docs/howitworks/)** | 10-chapter guide: overview through merge, replan, and lessons learned |

---

## License

MIT — See [LICENSE](LICENSE) for details.
