# Development Journey

How set-core evolved from a handful of git worktree scripts into a full autonomous orchestration framework.

---

## By The Numbers

| Metric | Value |
|--------|-------|
| Total commits | 1,287 |
| Capability specs | 363 |
| Python (engine + API) | 44,000 LOC |
| TypeScript (dashboard) | 12,700 LOC |
| E2E orchestration runs | 30+ |
| Quality gate types | 6 |

---

## Architecture Evolution

### Phase 1: Git Worktree Management

The first tools were simple shell scripts: `set-new`, `set-work`, `set-close`. They wrapped `git worktree` commands so that parallel development branches could be created and destroyed without manual bookkeeping. This solved the immediate problem of agents stepping on each other's code.

### Phase 2: Orchestration Engine

The core pipeline emerged: digest a spec, decompose it into changes with dependency graphs, dispatch each change to a worktree agent, and merge results back to main. The planner uses Claude to break a product spec into 5-15 implementation changes, each with explicit inputs/outputs and test requirements.

### Phase 3: Autonomous Sentinel Supervisor

A sentinel process was added to supervise the orchestrator end-to-end. It handles crash recovery, automatic restarts, stall detection via hash-based watchdogs, and PID management. This removed the need for a human to babysit multi-hour runs.

### Phase 4: Quality Gates

Six gate types were introduced to enforce correctness before any merge: unit test, build, E2E (Playwright), code review, smoke test, and spec coverage verification. Gates are deterministic — they run real commands and check exit codes, not LLM opinions. Every change must pass all applicable gates before it touches main.

### Phase 5: Web Dashboard and Real-Time Monitoring

A Next.js dashboard replaced the terminal TUI for monitoring orchestration runs. It shows live phase progress, token usage charts, change status with gate icons, session logs, and duration calculations. The dashboard reads from the same API that powers the engine, so it always reflects ground truth.

### Phase 6: Modular Plugin System

The project consolidated from three separate repos (set-core, set-project-base, set-project-web) into a single monorepo with a plugin architecture. Layer 1 (`lib/set_orch/`) provides abstract orchestration; Layer 2 (`modules/`) implements project-type specifics like Next.js detection, Playwright configuration, and Prisma patterns. External plugins register via Python entry points.

### Phase 7: Persistent Memory and Team Sync

A memory system was added so that agents retain context across sessions — known bugs, design decisions, user preferences. Memories are automatically injected into prompts based on topic relevance. Team sync enables cross-agent messaging so that parallel worktree agents can coordinate without conflicting.

---

## Key Insights

- **Agents need structure (OpenSpec), not just prompts.** Without a formal artifact workflow (proposal, design, spec, tasks, code), agents produce inconsistent output. OpenSpec forces each change through the same pipeline, making results predictable and verifiable.

- **Quality gates must be deterministic, not LLM-judged.** Early attempts at LLM-based code review as a merge gate were unreliable — the model would approve broken code or reject correct code depending on context length. Switching to real commands (`pnpm test`, `pnpm build`, `npx playwright test`) with binary pass/fail made the pipeline trustworthy.

- **Merge conflicts are the number one source of cascading failures.** In the CraftBrew run (15 changes), cross-cutting files like `prisma/schema.prisma` caused merge conflicts that lost entire model definitions. One bad merge resolution cascaded into runtime 500 errors across multiple features. Conflict handling must be automated and verified, not left to manual resolution.

- **Memory without save hooks is useless — agents do not save voluntarily.** When memory was opt-in ("call `remember` when you learn something"), agents almost never did. Automatic extraction from conversation transcripts, combined with topic-based injection on every prompt, made memory actually work.

- **E2E testing the orchestrator itself reveals bugs no unit test catches.** Running the full pipeline against a real project (scaffold, plan, dispatch, build, test, merge) exposed stall conditions, race conditions in parallel merges, and state machine bugs that were invisible in isolated unit tests. The 30+ E2E runs were the primary debugging tool for the engine.

---

<!-- specs: orchestration-engine, sentinel-dashboard, gate-profiles -->
