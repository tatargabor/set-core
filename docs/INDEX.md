# set-core Documentation

Navigation map for finding the right doc based on your role and goal.

## Where to Start

set-core v2.0.0 is a harness and fleet layer; the orchestration engine is dormant
([why](learn/from-orchestration-to-harness.md)). Read the current docs first; the
orchestration-era docs are kept as a record and marked so below.

| Role | Reading Path |
|------|-------------|
| **Running the fleet** | [fleet-machine-setup](guide/fleet-machine-setup.md) → [dashboard](guide/dashboard.md) → [openspec](guide/openspec.md) |
| **Contributor** | [from-orchestration-to-harness](learn/from-orchestration-to-harness.md) → [architecture](reference/architecture.md) → [plugins](reference/plugins.md) → [CONTRIBUTING](../CONTRIBUTING.md) |
| **Understanding the family** | [ecosystem](ecosystem.md) → [roadmap](roadmap.md) → [release notes](release/v2.0.0.md) |

## Guide (How-To)

| Doc | Description |
|-----|-------------|
| [fleet-machine-setup.md](guide/fleet-machine-setup.md) | Bring a machine up to the fleet: dashboard, bus, relay, auto-answer, handoff — with a check per step |
| [dashboard.md](guide/dashboard.md) | Web dashboard setup and usage |
| [openspec.md](guide/openspec.md) | Spec-driven development workflow |
| [worktrees.md](guide/worktrees.md) | Parallel development with git worktrees |

**Orchestration era — dormant, kept as a record:**

| Doc | Description |
|-----|-------------|
| [quick-start.md](guide/quick-start.md) | Install and run a first orchestration |
| [orchestration.md](guide/orchestration.md) | The autonomous pipeline walkthrough |
| [sentinel.md](guide/sentinel.md) | Supervisor setup and monitoring |
| [team-sync.md](guide/team-sync.md) | The git-based multi-agent coordination (retired; the bus is [set-agent-comm](https://github.com/tatargabor/set-agent-comm)) |
| [memory.md](guide/memory.md) | The memory subsystem — **removed** in v2.0.0 |

## Reference (Lookup)

| Doc | Description |
|-----|-------------|
| [cli.md](reference/cli.md) | Complete CLI command reference |
| [configuration.md](reference/configuration.md) | Config files, options, and provider credentials (`providers.json`) |
| [architecture.md](reference/architecture.md) | Technical design and layer model |
| [plugins.md](reference/plugins.md) | Project type system |
| [screenshot-pipeline.md](reference/screenshot-pipeline.md) | Auto-generated documentation screenshots |

## Learn (Deep Dives)

| Doc | Description |
|-----|-------------|
| [from-orchestration-to-harness.md](learn/from-orchestration-to-harness.md) | Why set-core changed direction in v2.0.0, what it is now, what was removed |
| [orchestration-pipeline.md](learn/orchestration-pipeline.md) | The orchestration pipeline as the README described it until v2.0.0 — dormant |
| [how-it-works.md](learn/how-it-works.md) | Orchestration pipeline internals (dormant) |
| [journey.md](learn/journey.md) | Development statistics and evolution |
| [benchmarks.md](learn/benchmarks.md) | E2E run results and metrics |
| [lessons-learned.md](learn/lessons-learned.md) | Production insights |

## Research (Investigations)

Dated technical deep-dives and empirical studies. See [research/README.md](research/README.md) for the full index.

| Doc | Topic |
|-----|-------|
| [token-optimization-analysis-2026-04-09.md](research/token-optimization-analysis-2026-04-09.md) | Claude token usage deep-dive, session-restart bug, cache tier decode |
| [template-divergence-elimination-2026-03-28.md](research/template-divergence-elimination-2026-03-28.md) | Consumer template drift cleanup |
| [orchestration-output-divergence-2026-03-27.md](research/orchestration-output-divergence-2026-03-27.md) | Cross-run structural divergence analysis |
| [e2e-testing-strategy.md](research/e2e-testing-strategy.md) | Consumer E2E runner design |
| [benchmark-results.md](research/benchmark-results.md) | Memory system benchmarks |
| [pi-mono-comparison.md](research/pi-mono-comparison.md) | Comparative analysis with Pi coding agent |

## FAQ

| Doc | Description |
|-----|-------------|
| [faq/](faq/) | Common questions from architects, CTOs, and senior engineers evaluating SET ([HTML](faq/faq.html), [Markdown](faq/index.md)) |

## Examples

| Doc | Description |
|-----|-------------|
| [minishop-walkthrough.md](examples/minishop-walkthrough.md) | Complete E2E orchestration example |
| [first-project.md](examples/first-project.md) | Getting started step by step |

## Deep Technical Reference

The [howitworks/en/](howitworks/en/) directory contains an 18-chapter technical reference of the (now dormant) orchestration pipeline, covering every stage — from input parsing through planning, execution, quality gates, merge, and replan.
