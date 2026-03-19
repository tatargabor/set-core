# Overview

## What Is Orchestration?

`set-orchestrate` is an autonomous orchestration system that independently plans, executes, and verifies development tasks starting from a software specification. The entire process begins with a single command:

```bash
set-orchestrate --spec docs/v3.md plan
set-orchestrate start
```

The system then:

1. **Understands** the specification (digest, requirement identifiers)
2. **Plans** the execution (changes, dependency graph)
3. **Executes tasks in parallel** (worktrees, AI agents)
4. **Verifies** quality (test, review, verify gates)
5. **Merges** the results (merge, post-merge pipeline)
6. **Continues** to the next phase (auto-replan)

\begin{keypoint}
The orchestrator is not a single large LLM call. It is a state machine-based system that checks agent status every 15 seconds, handles errors, and makes autonomous decisions about how to proceed.
\end{keypoint}

## The 5-Layer Model

The orchestration consists of five layers that build upon each other:

![The complete orchestration pipeline overview](diagrams/rendered/00-pipeline-overview.png){width=95%}

| Layer | Name | Responsibility | Key Modules |
|-------|------|---------------|-------------|
| **L1** | Input | Specification reading, configuration resolution | `config.sh`, `utils.sh` |
| **L2** | Planning | Digest generation, decomposition, DAG | `digest.sh`, `planner.sh` |
| **L3** | Execution | Worktree dispatch, Ralph loop, monitoring | `dispatcher.sh`, `monitor.sh`, `watchdog.sh` |
| **L4** | Quality | Test, review, verify, smoke, E2E gates | `verifier.sh` |
| **L5** | Delivery | Merge, post-merge, auto-replan | `merger.sh`, `monitor.sh` |

L1 and L2 are the "thinking" phase: the system understands the task and plans the approach. L3 is the "work" layer where AI agents actually write code — this is where most time and tokens are spent. L4 is "quality assurance," ensuring the completed work is actually good. L5 is "delivery": the result enters the main branch and the system decides whether to continue.

## Modular Architecture

`set-orchestrate` has a single entry point (`bin/set-orchestrate`), but the implementation is split across 14 source modules under `lib/orchestration/`:

```
bin/set-orchestrate          ← entry point, CLI parsing
lib/orchestration/
├── events.sh               ← JSONL event log
├── config.sh               ← configuration resolution
├── utils.sh                ← helper functions
├── state.sh                ← state management (JSON)
├── orch-memory.sh          ← memory integration
├── watchdog.sh             ← stall detection, escalation
├── planner.sh              ← decomposition, validation
├── builder.sh              ← base build health
├── dispatcher.sh           ← change lifecycle
├── verifier.sh             ← quality gates
├── merger.sh               ← merge, cleanup, archive
├── digest.sh               ← spec digest, coverage
├── reporter.sh             ← HTML report generation
└── monitor.sh              ← main monitor loop
```

Module loading order matters: `events.sh` is loaded first (every other module emits events), then `state.sh`, then the rest.

## State Files

The orchestrator stores its state in three main files:

| File | Contents |
|------|---------|
| `orchestration-plan.json` | The decomposition plan (changes, DAG, requirements) |
| `orchestration-state.json` | Runtime state (change statuses, token counts, merge queue) |
| `orchestration-summary.md` | Human-readable summary |

These files are created in the project root and are not version-controlled (they are in `.gitignore`).

## A Typical Run

A typical run of a medium project (10-15 changes, 3 parallel agents):

1. **Plan** (1-2 minutes): Spec processing, digest, decomposition
2. **Dispatch + Execution** (30-120 minutes): Parallel development in worktrees
3. **Verification** (continuous): Test + review for every completed change
4. **Merge** (continuous): Merge to main branch according to checkpoint policy
5. **Replan** (optional): If there is a next phase, replan and continue

The full pipeline can run for hours without supervision, while the watchdog and monitor loop handle error recovery.
