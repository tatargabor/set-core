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

Each layer is implemented in `lib/set_orch/` with clear module boundaries.

## Deep-Dive Chapters

The technical reference covers each stage in detail:

| Chapter | Topic | Key Concepts |
|---------|-------|-------------|
| [01 — Overview](../howitworks/en/01-overview.md) | Pipeline architecture | 5-layer model, state machine |
| [02 — Input](../howitworks/en/02-input-and-config.md) | Spec files, config | orchestration.yaml, directives |
| [03 — Digest](../howitworks/en/03-digest-and-triage.md) | Requirement extraction | Domain summaries, triage |
| [04 — Planning](../howitworks/en/04-planning.md) | Decomposition | DAG generation, phase ordering |
| [04b — OpenSpec](../howitworks/en/04b-openspec.md) | Artifact workflow | Proposal → specs → design → tasks |
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

- **Layer 1: Core** (`lib/set_orch/`) — abstract orchestration engine, never contains project-specific logic
- **Layer 2: Modules** (`modules/`) — project-type plugins (web/Next.js, example/Dungeon Builder)
- **Layer 3: External** — separate repos with their own `pyproject.toml`, registered via entry_points

See [Architecture Reference](../reference/architecture.md) for details.

---

*See also: [Journey](journey.md) · [Benchmarks](benchmarks.md) · [Lessons Learned](lessons-learned.md)*

<!-- specs: orchestration-engine, execution-model, state-mutations, modular-source-structure -->
