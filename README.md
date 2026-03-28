# set-core

**Autonomous multi-agent orchestration for Claude Code** — give it a spec, get merged features.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: Linux & macOS](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS-lightgrey.svg)]()
[![Website](https://img.shields.io/badge/Website-setcode.dev-22c55e)](https://setcode.dev)

set-core takes a markdown spec, decomposes it into independent changes, dispatches parallel Claude Code agents in git worktrees, runs quality gates on each, and merges the results. You provide the spec — it builds the app.

**Built with set-core, using set-core.** This project was developed using its own orchestration pipeline — every feature was planned through [OpenSpec](docs/guide/openspec.md), implemented by agents, and validated through quality gates. 363 capability specifications, 1,287 commits.

> Don't wait for perfection — start using it now. There will be bugs. But this is a self-healing system: the sentinel detects issues, investigates root causes, and dispatches fixes automatically. The more people use it, the faster it improves.

---

## See It In Action

**An agent working on a change — debugging, testing, fixing:**

<p align="center">
  <img src="docs/images/auto/web/agent-session-scroll.gif" width="90%" alt="Claude agent session — debugging, testing, and fixing code autonomously" />
</p>

**Input:** A markdown spec + Figma design

<p align="center">
  <img src="docs/images/auto/cli/spec-preview.png" width="48%" alt="Markdown spec — the input" />
  &nbsp;
  <img src="docs/images/auto/figma/storefront-design.png" width="48%" alt="Figma Make design — page structure and navigation" />
</p>

**Orchestration:** Phased execution, dependency DAG, quality gates on every change

<p align="center">
  <img src="docs/images/auto/web/tab-phases.png" width="48%" alt="Phases — dependency tree, gate badges, all merged" />
  &nbsp;
  <img src="docs/images/auto/web/tab-digest.png" width="48%" alt="Digest — 7 domains, 32 requirements, 84 acceptance criteria" />
</p>

**Output:** Running application — built entirely from the spec

<p align="center">
  <img src="docs/images/auto/app/products.png" width="48%" alt="MiniShop storefront" />
  &nbsp;
  <img src="docs/images/auto/figma/product-detail-design.png" width="48%" alt="Product detail — Figma design realized" />
</p>
<p align="center"><em>Spec + Figma → parallel agents → quality gates → working app. Zero intervention.</em></p>

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

## Key Features

| | Feature | Description |
|---|---|---|
| :gear: | **Full Pipeline** | Spec to merged code — digest, decompose, dispatch, verify, merge — hands-off. [Guide](docs/guide/orchestration.md) |
| :shield: | **Quality Gates** | Test, build, E2E, code review, spec coverage, and smoke — deterministic, not LLM-judged. [Guide](docs/guide/orchestration.md) |
| :brain: | **Persistent Memory** | Hook-driven cross-session recall — agents learn from each other. Infrastructure saves, not voluntary. [Guide](docs/guide/memory.md) |
| :bar_chart: | **Web Dashboard** | Real-time monitoring — orchestration state, agents, tokens, issues, learnings. [Guide](docs/guide/dashboard.md) |
| :clipboard: | **OpenSpec Workflow** | Structured artifact flow (proposal → design → spec → tasks → code) minimizes hallucination. [Guide](docs/guide/openspec.md) |
| :wrench: | **Self-Healing** | Issue pipeline: detect → investigate → fix → verify. The sentinel diagnoses before it acts. [Guide](docs/guide/sentinel.md) |
| :jigsaw: | **Plugin System** | Project-type plugins add domain rules, gates, templates, and conventions. [Docs](docs/reference/plugins.md) |

---

## What We're Solving

Most AI coding tools are nondeterministic — run the same prompt twice, get different results. set-core treats **reproducibility as an engineering problem**, not a hope.

| Challenge | Our Approach | Result |
|-----------|-------------|--------|
| **Output divergence** | [3-layer template system](docs/learn/journey.md) — templates lock structure, agents focus on logic | File structure divergence: 63% → 0% across paired runs |
| **Hallucination** | [OpenSpec workflow](docs/guide/openspec.md) — structured artifacts with requirements + acceptance criteria | Agents implement against spec, not imagination |
| **Quality roulette** | [Programmatic gates](docs/guide/orchestration.md) — exit codes, not LLM judgment. 7 gate types | Deterministic pass/fail |
| **Spec drift** | [Coverage tracking](docs/guide/openspec.md) — verifies "does it satisfy the spec?" not just "do tests pass?" | Auto-replan when coverage < 100% |
| **Failure recovery** | [Issue pipeline](docs/guide/sentinel.md) — detailed investigation before any fix. No guessing. | 30-second recovery, not hours |
| **Agent amnesia** | [Hook-driven memory](docs/guide/memory.md) — shared across worktrees, survives sessions | Zero voluntary saves → 100% capture via hooks |
| **Framework reliability** | [E2E scaffold testing](docs/learn/benchmarks.md) — the orchestrator tests itself | 30+ runs across 4 project scaffolds |

We're actively reducing nondeterminism through template optimization, divergence measurement, and configuration distribution across the core → module → scaffold → project layers. [Divergence research →](docs/learn/journey.md)

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

See [docs/guide/quick-start.md](docs/guide/quick-start.md) for detailed setup and first-run walkthrough.

---

## Technology

**Core orchestration:**

| Component | Technology |
|-----------|-----------|
| **Agent runtime** | [Claude Code](https://claude.ai/code) (Anthropic) |
| **Workflow** | [OpenSpec](https://github.com/fission-ai/openspec) — spec-driven artifact pipeline |
| **Isolation** | Git worktrees — real branches, real merges |
| **Engine** | Python, FastAPI, uvicorn |
| **Dashboard** | React, TypeScript, Tailwind CSS |
| **Memory** | shodh-memory (RocksDB + vector embeddings) |
| **Design bridge** | Figma MCP → design-snapshot.md → Tailwind tokens |

**Tooling ecosystem:**

| Tool | Purpose |
|------|---------|
| [set-spec-capture](https://github.com/tatargabor/set-spec-capture) | Capture specs from any source (web, PDF, conversation) |
| set-figma-fetch | Fetch Figma designs as Tailwind token snapshots |
| set-e2e-report | Generate benchmark reports from orchestration runs |

**Built-in modules** add domain-specific technology (Next.js, Prisma, Playwright for web; Soniox STT, Google TTS for voice). See [Plugins](docs/reference/plugins.md).

---

## Built & Battle-Tested

set-core is a **framework with a plugin system**. The core orchestration engine is open source. Project types — domain-specific rules, templates, and conventions — can be public or private.

The **web project type** (Next.js, Prisma, Playwright) ships built-in and is validated through synthetic E2E orchestration runs that simulate real development environments — reproducible, measurable, tracked.

**Custom project types in development** include voice agent delivery (Soniox TTS/STT with spec-driven customer interaction), and others not yet public. The plugin architecture lets anyone create their own domain-specific type with custom gates, templates, and conventions.

| Metric | Value |
|--------|-------|
| Development | 950+ hours across 79 days |
| Commits | 1,294 (~16/day) |
| Capability specs | 363 |
| Codebase | 134K LOC (59K Python, 15K Shell, 14K TypeScript, 23K specs, 22K docs+templates) |
| Autonomous agent runtime | 720+ hours continuous operation |
| MiniShop benchmark | 6/6 merged, 0 interventions, 1h 45m |

**3 months. 950+ hours. Worth every one.** Full journey, benchmarks, and lessons: [docs/learn/journey.md](docs/learn/journey.md)

---

## Why This Matters

**Systems like SET can do the work of a full development team** — given the right specification and properly developed project types. Period.

This is not the future. This is the present. The sooner we move in this direction, the sooner we'll see what software development actually becomes — instead of clinging to the assumption that manual development or even manual code review should remain the default.

### Don't blame the model

Claude Code is extraordinarily capable. But we can't expect it to guess what we haven't specified. When the model fills in gaps we left empty, we call it "hallucination" — but most of the time, it's **underspecification on our side**. The frustration of repeated errors, unexpected behavior, inconsistent output — 90% of this comes from insufficient context, not model limitation.

And even with detailed, multi-hundred-page specifications, we cannot guarantee that the model treats every character with equal priority during implementation. This is precisely why systems like SET exist: to **enforce, verify, and check** that the model understood and executed what we intended. OpenSpec structures the work. Quality gates verify the output. The sentinel investigates before it fixes. No guessing.

### Enterprise is next

Banks, government, defense, regulated industries — they can't use cloud-hosted models today. But this will change. On-premise models, secure multi-tenant systems, hybrid architectures — the infrastructure is coming. Some organizations are already preparing.

**The responsible thing for every enterprise is to prepare now** — before the models arrive on their infrastructure. Learn orchestration patterns. Build project types for your domain. Develop the muscle memory for spec-driven development. Don't wait for the infrastructure to be ready; be ready when it arrives.

### This needs a community

We built set-core to solve our own problems. The web project type is public and battle-tested. But the real power comes from **domain-specific project types** — fintech with IDOR rules, healthcare with HIPAA compliance, e-commerce with payment flow gates.

Model providers (Anthropic included) will build orchestration into their platforms — we welcome that. These middleware layers are destined to become first-party features. But that doesn't mean we shouldn't build them ourselves: this is how we **shape the tools to our needs** and accumulate knowledge that vendor-generic solutions can't provide.

**Start now.** There will be bugs. But this is a self-healing system — the sentinel detects, investigates, and fixes. The more people use it, the faster it improves.

[Join us →](https://github.com/tatargabor/set-core/issues) · [Email](mailto:gabor@setcode.dev)

---

## Documentation

| Section | Contents |
|---------|----------|
| **[Guide](docs/guide/)** | Quick start, orchestration, sentinel, worktrees, OpenSpec, memory, dashboard |
| **[Reference](docs/reference/)** | CLI tools, configuration, architecture, plugins |
| **[Learn](docs/learn/)** | How it works, development journey, benchmarks, lessons learned |
| **[Examples](docs/examples/)** | MiniShop walkthrough, first project setup |
| **[Deep Dive](docs/howitworks/)** | 18-chapter technical reference covering every pipeline stage |

---

## License

MIT — See [LICENSE](LICENSE) for details.

**Website:** [setcode.dev](https://setcode.dev) · **GitHub:** [tatargabor/set-core](https://github.com/tatargabor/set-core)
