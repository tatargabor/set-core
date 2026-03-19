# shodh-memory Benchmark Protocol

A reproducible benchmark for measuring the impact of persistent developer memory (shodh-memory) on AI agent effectiveness across independent sessions.

## Overview

Two autonomous agents implement the same multi-change project (CraftBazaar — a multi-vendor artisan marketplace). One agent runs without memory (baseline), the other with shodh-memory enabled. Both use identical tooling (set-core, OpenSpec, set-loop) and receive the same task descriptions.

The project is designed with 6 sequential changes where early decisions cascade into later ones, creating natural traps that cross-session memory can help avoid.

## What's in this directory

| File/Directory | Purpose |
|---|---|
| `project-spec.md` | CraftBazaar domain specification (agent input) |
| `changes/01-*.md` through `06-*.md` | Per-change definitions with agent input + evaluator notes |
| `claude-md/baseline.md` | CLAUDE.md for Run A (no memory) |
| `claude-md/with-memory.md` | CLAUDE.md for Run B (with memory) |
| `run-guide.md` | Step-by-step execution instructions |
| `scoring-rubric.md` | Evaluation criteria and scoring methodology |
| `diagnostic-framework.md` | Memory gap analysis methodology |
| `templates/` | Annotation, metrics, and report templates |
| `collect-results.md` | Post-run results collection guide |
| `init-baseline.sh` | Bootstrap script for Run A (no memory) |
| `init-with-memory.sh` | Bootstrap script for Run B (with memory) |

## Quick Start

```bash
# 1. Bootstrap both runs
./benchmark/init-baseline.sh      # → ~/benchmark/run-a/craftbazaar
./benchmark/init-with-memory.sh   # → ~/benchmark/run-b/craftbazaar

# 2. Start runs (two terminals)
cd ~/benchmark/run-a/craftbazaar
set-loop start "Build CraftBazaar changes 01-06" --max 20 --stall-threshold 3 --done manual

cd ~/benchmark/run-b/craftbazaar
set-loop start "Build CraftBazaar changes 01-06" --max 20 --stall-threshold 3 --done manual

# 3. After both complete, collect results
# See collect-results.md for agent-assisted evaluation
```

See `run-guide.md` for full details, prerequisites, and monitoring.
