# set-core

**Autonomous multi-agent orchestration for Claude Code** — give it a spec, get merged features.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: Linux & macOS](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS-lightgrey.svg)]()

---

## Why set-core?

Claude Code is already incredibly powerful. set-core asks: *how far can we push it?*

You have a spec with 10 features. Hand it to set-core — parallel agents decompose, implement, test, and merge all of them while you sleep. Some of these capabilities will eventually land in Claude Code natively (like Agent Teams). We're exploring the frontier now, learning what works in production, and sharing the patterns.

**set-core is a full autonomous pipeline:**

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

### What we've learned pushing the limits

| Capability | What set-core adds |
|---|---|
| **Full pipeline** | Spec → digest → decompose → parallel dispatch → verify → merge — hands-off |
| **Design bridge** | Figma → `design-snapshot.md` → tokens + hierarchy injected into agent context |
| **Persistent memory** | Cross-session semantic recall — agents learn from each other |
| **Structured workflow** | OpenSpec: proposal → design → spec → tasks → code — keeps agents on track |
| **Quality gates** | Jest/Build/E2E/Review/Smoke per change, with per-change-type gate profiles |
| **Autonomous supervision** | Sentinel: crash recovery, progress monitoring, auto-restart, auto-replan |
| **Zero infrastructure** | File-based, no daemon, no database, no external service |

---

## Quick Start

```bash
# Install
git clone https://github.com/tatargabor/set-core.git
cd set-core && ./install.sh

# Register your project
cd ~/my-project && set-project init --project-type web --template nextjs

# Run autonomous orchestration (from a Claude Code session)
/set:sentinel --spec docs/my-spec.md --max-parallel 2
```

Or start simple — just use worktrees:

```bash
set-new my-feature        # create isolated worktree
set-work my-feature       # open in editor + start Claude Code
# ... work ...
set-merge my-feature      # merge back to main
```

See [Getting Started](docs/getting-started.md) for the full guide.

---

## Orchestration Pipeline

The orchestration pipeline is the heart of set-core. It takes a spec file and autonomously builds, tests, and merges a complete application.

<!-- TODO: screenshot — orchestration TUI showing active changes, progress bars, quality gate status -->
![Orchestrator workspace — TUI, memory dashboard, agent terminal](docs/images/orchestrator-workspace.png)

### Pipeline Stages

```
┌─────────┐    ┌──────────┐    ┌───────────┐    ┌──────────┐    ┌─────────┐    ┌────────┐
│  Input   │───►│  Digest  │───►│ Decompose │───►│ Dispatch │───►│ Verify  │───►│ Merge  │
│          │    │          │    │ & Plan    │    │ & Execute│    │ Gates   │    │        │
│ spec.md  │    │ require- │    │ changes + │    │ worktree │    │ test,   │    │ merge  │
│ figma    │    │ ments,   │    │ DAG,      │    │ per      │    │ build,  │    │ post-  │
│ config   │    │ domains  │    │ phases    │    │ change   │    │ e2e,    │    │ merge  │
│          │    │          │    │           │    │          │    │ review  │    │ smoke  │
└─────────┘    └──────────┘    └───────────┘    └──────────┘    └─────────┘    └────────┘
```

<!-- TODO: screenshot — set-orchestrate architecture diagram showing all modules -->

**Spec digest** — For complex multi-file specs, the system first generates a structured digest: domain summaries, requirement IDs, dependency graph, and coverage tracking. This ensures no requirements are lost during decomposition.

**Decompose & plan** — An LLM decomposes the spec into independent changes with a dependency DAG. Each change gets a scope definition, expected files, test expectations, and relevant design tokens from Figma.

<!-- TODO: screenshot — example decompose output showing changes and dependency graph -->

**Dispatch & execute** — Each change gets its own git worktree. A Ralph Loop runs Claude Code autonomously: creates OpenSpec artifacts (proposal → design → spec → tasks), then implements iteratively with progress tracking.

**Quality gates** — Before merge, every change passes through configurable gates:

| Gate | What it checks | Configurable via |
|------|---------------|-----------------|
| **Test** | Jest/Vitest unit tests pass | `test_command` |
| **Build** | Project builds without errors | `build_command` |
| **E2E** | Playwright end-to-end tests pass | `e2e_command` |
| **Code review** | LLM review for security, quality | gate profiles |
| **Spec coverage** | Implementation matches spec requirements | gate profiles |
| **Smoke test** | Post-merge sanity check on main | `smoke_command` |

**Gate profiles** — Different change types get different gate configurations. A `foundational` change (project setup) doesn't need E2E tests. A `schema` change doesn't require test files. Configure via `gate_overrides()` in your project type plugin.

**Merge & delivery** — Verified changes merge to main. Post-merge pipeline runs dependency install, smoke tests, and scope verification. Auto-replan checks if all spec requirements are covered.

### Design Bridge (Figma Integration)

When a Figma MCP server is configured, the orchestration pipeline automatically:

1. **Fetches** a `design-snapshot.md` before planning — design tokens, component hierarchy, frame structure
2. **Injects** relevant tokens (colors, spacing, typography) into each change's agent context
3. **Extracts** Figma source files (`docs/figma-raw/`) for component-level ground truth
4. **Verifies** design compliance in the code review gate — token mismatches are flagged

<!-- TODO: screenshot — design-snapshot.md example showing extracted tokens and component hierarchy -->

```
Figma ──► set-figma-fetch ──► design-snapshot.md ──► planner (tokens per change)
                                                 ──► dispatcher (hierarchy per agent)
                                                 ──► verifier (compliance check)
```

---

## Core Features

**[Sentinel & Orchestration](docs/sentinel.md)** — Decomposes a spec into independent changes, dispatches each to its own worktree, monitors progress, merges with verification gates. The sentinel handles crashes, auto-approves, and summarizes. [Pipeline details](docs/orchestration.md) | [How It Works guide](docs/howitworks/en/01-overview.md)

**[Developer Memory](docs/developer-memory.md)** — Per-project semantic recall powered by [shodh-memory](https://github.com/shodh-ai/shodh-memory). Agents save decisions and learnings as they work; future agents recall them automatically via 5-layer hooks. MCP tools for deeper memory interactions.

**[OpenSpec Workflow](docs/openspec.md)** — Structured spec-driven development: `/opsx:new` → `/opsx:ff` → `/opsx:apply` → `/opsx:verify` → `/opsx:archive`. Prevents agents from going off-track with artifact tracking.

**[Worktrees](docs/worktrees.md)** — Git worktree lifecycle with editor integration and Claude Code auto-launch. CLI (`set-new`, `set-work`, `set-merge`) or agent skills (`/set:new`, `/set:merge`).

**[Ralph Loop](docs/ralph.md)** — Autonomous agent execution. Runs Claude Code in iterations through task lists with configurable limits and progress-based trend detection.

**[Web Dashboard](docs/gui.md)** — Browser-based dashboard (React + TypeScript) for orchestration monitoring, agent status, memory browser. Desktop GUI (PySide6) for always-on-top compact view.

**[Team Sync](docs/team-sync.md) · [MCP Server](docs/mcp-server.md)** — Cross-machine coordination via `set-control` git branch. MCP server exposes worktree status, memory tools, and Ralph progress to agents.

### When to use what

| Situation | Tool |
|---|---|
| Single agent, single project | Claude Code alone is great — start there |
| 2+ agents or switching projects | Web Dashboard + `set-work` |
| Structured feature development | OpenSpec (`/opsx:new` → `/opsx:apply`) |
| Task list to grind through | Ralph Loop (`set-loop start`) |
| Multiple changes from a spec | Sentinel (`/set:sentinel --spec`) |
| Agents learning across sessions | Developer Memory (`set-memory`) |

---

## Web Dashboard

The set-web dashboard shows running projects, orchestration state, agent status, and logs in a browser. Responsive design works on desktop and mobile.

<!-- TODO: screenshot — set-web desktop view showing orchestration dashboard with agent cards, progress bars -->

<!-- TODO: screenshot — set-web mobile view (phone) showing compact orchestration status via Tailscale -->

**Start locally:**

```bash
cp .env.example .env
# Edit .env — set SET_WEB_PORT (default: 7400) and SET_TAILSCALE_HOSTNAME
set-orch-core serve                    # http://localhost:7400
```

**As a systemd service:**

```bash
cp templates/systemd/set-web.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now set-web
```

**Mobile access** — The dashboard works on phones via [Tailscale](https://tailscale.com). Set `SET_TAILSCALE_HOSTNAME` in `.env`, run `sudo tailscale serve --bg --http 80 http://localhost:7400`, then open in Chrome on your phone. HTTP is used because Tailscale's auto-provisioned certs can trigger Certificate Transparency errors on Android — the WireGuard tunnel already encrypts all traffic.

---

## Benchmark: MiniShop E2E

We run a repeatable benchmark: build a **Next.js webshop from a single spec file** — products, cart, checkout, admin auth, admin CRUD, product variants — with autonomous orchestration.

### Latest: Run #15 (8/8 merged)

```
Spec (with Figma design) ──► 8 changes planned ──► parallel agents ──► all 8 merged

Wall clock:          2h 45m
Changes merged:      8/8 (100%)
Sentinel interventions: 5 (merge conflicts, stall recovery)
Total tokens:        5.28M
Commits:             43
```

### Run history

| Metric | Run #4 | Run #13 | Run #15 |
|---|---|---|---|
| Changes merged | 6/6 | 6/6 | **8/8** |
| Wall clock | 1h 45m | 4h 24m | 2h 45m |
| Human interventions | 0 | 5 | 5 |
| Quality gates | build+test+E2E | +review+security | +design bridge+gate profiles |
| Spec scope | 6 features | 6 features | **8 features** (+ EAV variants) |
| Tokens | 2.7M | 2.18M | 5.28M |
| Framework bugs found | 3 | 5 | 6 |

**Run #4** — First fully autonomous run (zero interventions). **Run #13** — Added code review gate + web security rules; caught IDOR vulnerabilities. **Run #15** — Added design bridge (Figma), gate profiles, uncommitted work guard, expanded spec.

Every change passes: **Test → Build → E2E → Code Review → Spec Coverage → Merge → Post-merge Smoke.**

Full details: **[Run #4 Benchmark Report](docs/benchmark-minishop-run4.md)** | **[E2E Findings Log](tests/e2e/minishop/)**

---

## E2E Test Architecture

E2E tests validate the full orchestration pipeline against real projects. Each test is a self-contained scaffold with a spec, optional Figma design data, and orchestration config.

### Spec Structure (how to write orchestratable specs)

set-core orchestrates from **markdown spec files**. Any project can be orchestrated if the spec follows this structure:

```markdown
# My Project v1 — Feature Spec

> Tech stack description (Next.js 14+, Prisma, shadcn/ui, etc.)

## Design
**Figma Design:** https://www.figma.com/make/...
**Local design snapshot:** `docs/figma-raw/.../`

## Starting Point
What exists already vs. what agents create from scratch.

## Dependencies (package.json)
Exact dependencies agents should use.

## Feature: Products Page
### Requirements
- Product grid with responsive layout (3-col desktop, 1-col mobile)
- Price formatting with currency symbol
- Stock badge (In Stock / Out of Stock)

### Database (Prisma schema)
model Product {
  id    Int    @id @default(autoincrement())
  name  String
  price Float
  ...
}

### Pages & Routes
- `/` — product listing (server component)
- `/products/[id]` — product detail

### Tests
- Unit: product display, price formatting
- E2E: navigation, filter, responsive layout

## Feature: Shopping Cart
...
```

<!-- TODO: screenshot — example spec.md file structure in editor, showing feature sections -->

### Test Scaffolds

| Scaffold | Spec | Changes | Purpose |
|----------|------|---------|---------|
| **MiniShop** (`tests/e2e/scaffold/`) | Next.js webshop | 6-8 | Core pipeline validation — products, cart, checkout, auth, admin |
| **CraftBrew** (`tests/e2e/scaffold-complex/`) | Multi-phase coffee app | 14+ | Complex spec handling — i18n, subscriptions, reviews, promotions |

Each scaffold contains:
```
tests/e2e/scaffold/
├── docs/
│   ├── v1-minishop.md          # The spec file
│   ├── design-snapshot.md       # Pre-fetched Figma design tokens
│   └── figma-raw/              # Figma source files (component hierarchy, mockdata)
```

### Running E2E tests

```bash
# MiniShop (standard)
./tests/e2e/run.sh /tmp/minishop-test

# CraftBrew (complex, multi-phase)
./tests/e2e/run-complex.sh /tmp/craftbrew-test

# In the test project, start orchestration
cd /tmp/minishop-test
set-sentinel --spec docs/v1-minishop.md
```

See [E2E Test Guide](tests/e2e/E2E-GUIDE.md) for sentinel monitoring, partial reset, deploy workflow, and run history.

---

## How It Works (Detailed Guide)

The `docs/howitworks/` directory contains a comprehensive guide to the orchestration pipeline, available in English and Hungarian:

| Chapter | Topic |
|---------|-------|
| [01 - Overview](docs/howitworks/en/01-overview.md) | 5-layer model, modular architecture |
| [02 - Input & Config](docs/howitworks/en/02-input-and-config.md) | Spec files, orchestration.yaml, directives |
| [03 - Digest & Triage](docs/howitworks/en/03-digest-and-triage.md) | Requirement extraction, domain summaries |
| [04 - Planning](docs/howitworks/en/04-planning.md) | LLM decomposition, dependency DAG, design token injection |
| [04b - OpenSpec](docs/howitworks/en/04b-openspec.md) | Artifact workflow inside each change |
| [05 - Execution](docs/howitworks/en/05-execution.md) | Worktree dispatch, Ralph loop, agent lifecycle |
| [06 - Monitor & Watchdog](docs/howitworks/en/06-monitor-and-watchdog.md) | Progress tracking, stall detection, PID guard |
| [06b - Sentinel](docs/howitworks/en/06b-sentinel.md) | Crash recovery, auto-restart, supervision |
| [07 - Quality Gates](docs/howitworks/en/07-quality-gates.md) | Test/build/E2E/review/smoke gates, gate profiles |
| [08 - Merge & Delivery](docs/howitworks/en/08-merge-and-delivery.md) | Merge pipeline, post-merge, conflict resolution |
| [09 - Replan & Coverage](docs/howitworks/en/09-replan-and-coverage.md) | Auto-replan, spec coverage tracking |
| [09b - Lessons Learned](docs/howitworks/en/09b-lessons-learned.md) | Production insights from E2E runs |
| [10 - Reference](docs/howitworks/en/10-reference.md) | Module reference, configuration options |

---

## Project Types & Convention Plugins

When multiple agents work on a codebase, they need shared conventions — not copied into CLAUDE.md (which wastes context every turn), but loaded on demand when relevant files are touched.

**Project type plugins** solve this:

```
CoreProfile (set-core built-in)   Universal rules (file size, secrets, TODOs)
  └── modules/web/                 Web domain rules (SEO, a11y, security, i18n, ...)
        └── your-org-web           Organization-specific rules (external plugin)
```

```bash
set-project init --project-type web --template nextjs
```

This deploys path-scoped convention files, verification rules, orchestration directives, and gate overrides into the project. Agents only see the rules relevant to the files they're editing — an agent working on `prisma/schema.prisma` gets data-model conventions, not UI rules.

Available project types (monorepo):
- **CoreProfile** (`lib/set_orch/profile_types.py`, `profile_loader.py`) — `ProjectType` ABC, universal rules, resolver, template deploy, feedback system (absorbed from set-project-base)
- **WebProjectType** (`modules/web/set_project_web/`) — 13 convention rule files, 11 verification rules, 7 orchestration directives, gate overrides, Figma design integration
- **Example** (`modules/example/`) — Dungeon Builder example plugin

External plugins still work via `entry_points` in separate repos. Profile resolution: entry_points → direct import → built-in modules/ → NullProfile.

See [Plugin Architecture](docs/plugins.md) for customization and layering.

---

## Fork & Adapt

Our primary focus is web development — that's where we push hardest. But set-core is project-agnostic by design. The base tooling (worktrees, memory, orchestration) works on any codebase: APIs, mobile apps, data pipelines, research projects. Built from months of production work across web apps, sensor systems, education platforms, and more.

**Why fork or study it:**
- Battle-tested orchestration patterns from real client projects
- 40+ archived OpenSpec changes showing real development history
- Modular — cherry-pick what you need (CLI, memory, orchestration, web dashboard)
- Well-structured `.claude/` setup (hooks, skills, commands, agents) ready to adapt
- Comprehensive [How It Works](docs/howitworks/en/01-overview.md) guide for understanding the architecture
- Continuously updated as Claude Code's capabilities expand

Built and used in production by [ITLine Kft.](https://itline.hu).

### On the horizon

Claude Code is evolving fast — Agent Teams, persistent memory, and better autonomous loops are all coming. We're not racing against these; we're exploring ahead of them. When they land natively, we'll integrate or retire gracefully. The patterns and production learnings remain valuable either way.

---

## Installation

**Prerequisites:** Git, Python 3.10+, jq, Node.js

```bash
git clone https://github.com/tatargabor/set-core.git
cd set-core && ./install.sh
```

The installer handles everything: CLI symlinks, shell completions, MCP server config, GUI dependencies, and optional memory system setup. See [Getting Started](docs/getting-started.md) for platform-specific notes.

### Platform & Editor Support

| Platform / Tool | Status |
|---|---|
| **Linux** | Primary development platform — tested on Ubuntu 22.04+ |
| **macOS** | Partial — core functionality works, contributors improving parity |
| **Zed** | Primary editor, best tested |
| **VS Code / Cursor / Windsurf** | Supported via `set-config editor set` |
| **Claude Code** | Integrated — auto-launch, MCP, skill hooks |

> **Note:** Feature development is Linux-first. macOS is supported and used in production, but some platform-specific behavior (e.g. window management, process signals) may differ. We welcome macOS-focused contributions.

---

## Docs

| Area | Links |
|------|-------|
| **Getting Started** | [Getting Started](docs/getting-started.md) · [Configuration](docs/configuration.md) · [CLI Reference](docs/cli-reference.md) |
| **Orchestration** | [Sentinel](docs/sentinel.md) · [Orchestration](docs/orchestration.md) · [How It Works](docs/howitworks/en/01-overview.md) |
| **Workflow** | [OpenSpec](docs/openspec.md) · [Worktrees](docs/worktrees.md) · [Ralph Loop](docs/ralph.md) |
| **Infrastructure** | [Memory](docs/developer-memory.md) · [MCP Server](docs/mcp-server.md) · [Team Sync](docs/team-sync.md) |
| **UI** | [Web Dashboard / GUI](docs/gui.md) · [Architecture](docs/architecture.md) |
| **Plugins** | [Project Setup](docs/project-setup.md) · [Plugins](docs/plugins.md) |
| **Testing** | [E2E Test Guide](tests/e2e/E2E-GUIDE.md) · [Benchmark Report](docs/benchmark-minishop-run4.md) · [E2E Findings](tests/e2e/minishop/) |

---

<details>
<summary><strong>Alternatives & Comparison</strong></summary>

The Claude Code multi-agent space is evolving fast. Tools fall into three categories:

**Session managers** — run N agents, switch between them (claude-squad, agent-deck)
**Plugins/enhancements** — make Claude Code smarter from within (oh-my-claudecode, wshobson/agents)
**Spec-driven orchestrators** — decompose work, dispatch, verify, merge (set-core, ccpm, overstory)

Note: Claude Code's native Agent Teams (experimental) is moving fast — many set-core patterns will likely become built-in. We see this as validation, not competition. The value is in what we've learned building production orchestration, and this repo shares those patterns openly.

| Tool | Stars | Category | Focus |
|---|---|---|---|
| [ruflo](https://github.com/ruvnet/ruflo) | ~20k | Platform | Enterprise swarm platform, 60+ agents, MCP |
| [oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) | ~8.5k | Plugin | 5 execution modes, 32 agents, auto-resume |
| [ccpm](https://github.com/automazeio/ccpm) | ~7.6k | Orchestrator | GitHub Issues as task DB, spec-driven |
| [claude-squad](https://github.com/smtg-ai/claude-squad) | ~6.2k | Session mgr | TUI for tmux+worktree sessions (Go) |
| [agent-orchestrator](https://github.com/ComposioHQ/agent-orchestrator) | ~3.9k | Orchestrator | Agent-agnostic, runtime-agnostic |
| [automaker](https://github.com/AutoMaker-Org/automaker) | ~3k | Desktop app | Electron Kanban + Claude Agent SDK |
| [agent-deck](https://github.com/asheshgoplani/agent-deck) | ~1.4k | Session mgr | TUI+Web, session forking, MCP pooling |
| [overstory](https://github.com/jayminwest/overstory) | ~290 | Orchestrator | Runtime-agnostic, SQLite messaging, FIFO merge |

### Feature comparison

```
                     Spec→Merge  Worktree  Auto   Memory  Structured   Crash    Design   GUI
                     Pipeline    Isolation Loop   Recall  Workflow     Recovery Bridge
──────────────────────────────────────────────────────────────────────────────────────────────
set-core              Y          Y        Y      Y       Y (OpenSpec)  Y       Y (Figma)  Y
ccpm                  Y          Y        Y      -       Y (PRD→Issue) -       -          -
oh-my-claudecode      -          -        Y      -       -             Y       -          -
claude-squad          -          Y        Y      -       -             -       -         TUI
agent-orchestrator    Y          Y        ~      -       -             -       -          -
automaker             Y          Y        Y      -       -             -       -          Y
overstory             ~          Y        Y      -       -             Y       -         TUI
```

**set-core is the only tool combining full spec-to-merge pipeline, persistent cross-session memory, design bridge, and structured spec workflow.** Closest competitor is ccpm (spec-driven, parallel agents) but it requires GitHub Issues as its task store and lacks memory, design integration, and sentinel supervision.

</details>

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and pull request guidelines.

## Acknowledgements

Built by [Gabor Tatar](https://itline.hu) (ITLine Kft.) and used across production projects.

Special thanks: [BlackBelt](https://blackbelt.hu) · [AIOrigo](https://aiorigo.com) · [MKIK](https://mkik.hu)

## License

MIT — See [LICENSE](LICENSE) for details.
