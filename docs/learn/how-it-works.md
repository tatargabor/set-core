[< Back to Index](../INDEX.md)

# How It Works — Pipeline Internals

This page provides an overview of the orchestration pipeline internals. For the complete technical deep-dive, see the [18-chapter technical reference](../howitworks/en/01-overview.md).

## The 5-Layer Model

```
Layer 1: Input        spec.md + config → digest → requirements
Layer 2: Planning     requirements → dependency DAG → phased changes
Layer 3: Execution    changes → worktrees → Ralph Loop agents
Layer 4: Verification quality gates → test/build/E2E/review/smoke
Layer 5: Delivery     merge → post-merge verify → replan → next phase
```

Each layer is implemented in `lib/set_orch/` with clear module boundaries. The pipeline runs in a continuous loop: after all changes in a phase merge, the next phase starts. If a change fails verification, the replan engine can decompose it into smaller changes and re-dispatch.

![Dashboard overview showing pipeline state](../images/auto/web/dashboard-overview.png)

## Cross-Cutting Subsystems

Layered alongside the pipeline:

- **Design pipeline** (`set-design-import`, `design-manifest.yaml`, `design-fidelity-gate`) — pulls a v0.app export into a structured manifest, slices a per-change `design.md` into each agent's input, and runs a JSX structural parity check at merge to block visual divergence. Replaces the legacy Figma `.make` flow.
- **Issue lifecycle** (`fix-iss`, `IssueRegistry`, circuit-breakers) — surfaces gate failures, supervisor anomalies, and circuit-breaker escalations (`merge_stalled`, `token_runaway`, `poisoned_stall`) as first-class issues. The investigator agent diagnoses, the resolver fixes, and the parent change auto-recovers from `failed:*` once the fix-iss child resolves.
- **Forensics** (`set-run-logs`, `/set:forensics` skill, activity dashboard) — every gate run, agent decision, LLM call, and sub-agent placed on a real-time axis. Per-iteration session attribution via `AGENT_SESSION_DECISION` events; per-gate spans reconstructed from `VERIFY_GATE` events.
- **Cost tracking** — USD per change / per gate / per session, with `cache_read_input_tokens` correctly excluded from billed input. Drives the per-change token-runaway breaker.
- **Memory layer** — 5-layer hooks inject context per tool call, save at session boundaries, surface relevant past errors automatically. `SET_MEMORY_HOOKS=lite` mode for low-context sessions.

## Deep-Dive Chapters

The technical reference is organized into prefatory material (chapters 00) and 12 core pipeline chapters (01--10):

### Prefatory

| Chapter | Topic | Key Concepts |
|---------|-------|-------------|
| [00 — Meta](../howitworks/en/00-meta.md) | Book structure | Chapter map, reading guide |
| [00b — Preface](../howitworks/en/00b-preface.md) | Why this book | Motivation and audience |
| [00c — Why](../howitworks/en/00c-why.md) | Problem statement | Why autonomous orchestration |
| [00d — Development](../howitworks/en/00d-development.md) | How it was built | Self-hosting, bootstrap story |
| [00e — Ecosystem](../howitworks/en/00e-ecosystem.md) | Surrounding tools | CLI, GUI, MCP, plugins |

### Pipeline

| Chapter | Topic | Key Concepts |
|---------|-------|-------------|
| [01 — Overview](../howitworks/en/01-overview.md) | Pipeline architecture | 5-layer model, state machine |
| [02 — Input](../howitworks/en/02-input-and-config.md) | Spec files, config | orchestration.yaml, directives |
| [03 — Digest](../howitworks/en/03-digest-and-triage.md) | Requirement extraction | Domain summaries, triage |
| [04 — Planning](../howitworks/en/04-planning.md) | Decomposition | DAG generation, phase ordering |
| [04b — OpenSpec](../howitworks/en/04b-openspec.md) | Artifact workflow | Proposal, specs, design, tasks |
| [05 — Execution](../howitworks/en/05-execution.md) | Dispatch, Ralph Loop | Worktree agents, iteration |
| [06 — Monitor](../howitworks/en/06-monitor-and-watchdog.md) | Progress tracking | 15s poll cycle, stall detection |
| [06b — Sentinel](../howitworks/en/06b-sentinel.md) | Supervisor | Crash recovery, checkpoints |
| [07 — Gates](../howitworks/en/07-quality-gates.md) | Verification | Test/build/E2E/review/smoke |
| [08 — Merge](../howitworks/en/08-merge-and-delivery.md) | Delivery | FF-only merge, conflict resolution |
| [09 — Replan](../howitworks/en/09-replan-and-coverage.md) | Coverage | Auto-replan, spec tracking |
| [09b — Lessons](../howitworks/en/09b-lessons-learned.md) | Production insights | Real-world findings |
| [10 — Reference](../howitworks/en/10-reference.md) | State machine | Change lifecycle, CLI |

## Architecture

The codebase follows a 3-layer architecture:

```
Layer 1: Core (lib/set_orch/)
  Abstract orchestration engine. Profile system, dispatcher, merger,
  verifier, planner, monitor, events. Never contains project-specific
  logic — no web patterns, no framework detection, no language-specific
  rules.

Layer 2: Modules (modules/)
  Project-type plugins that ship with set-core.
  - modules/web/   -> WebProjectType: Next.js, Playwright, Prisma
  - modules/example/ -> DungeonProjectType: reference implementation
  Each module is a standalone pip-installable package.

Layer 3: External (separate repos)
  Private or community plugins registered via Python entry_points.
  Entry_points take priority over built-in modules.
  Example: set-project-fintech with PCI compliance checks.
```

The profile system is the extension point. When the orchestrator needs to know how to run tests, it calls `profile.detect_test_command()`. When it needs forbidden patterns for the lint gate, it calls `profile.get_forbidden_patterns()`. Core defines the interface; modules provide the implementation.

See the [Reference section](../reference/README.md) for CLI and configuration details, or [00e — Ecosystem](../howitworks/en/00e-ecosystem.md) for how the layers connect.

---

*See also: [Journey](journey.md) · [Benchmarks](benchmarks.md) · [Lessons Learned](lessons-learned.md)*

<!-- specs: orchestration-engine, execution-model, state-mutations, modular-source-structure -->
