## Context

The shodh-memory system is fully integrated into set-core — skills save and recall memories, CLAUDE.md has proactive memory hooks, and the CLI supports remember/recall/forget operations. However, there's no empirical evidence that this memory layer actually helps AI agents perform better across independent sessions. We need a controlled benchmark to prove (or disprove) this value.

The benchmark uses a separate "test project" (CraftBazaar — a multi-vendor marketplace built with Next.js + Prisma + SQLite) that is complex enough to create natural traps where cross-session memory matters. The benchmark protocol, scoring rubric, and project specification live in set-core as documentation. The actual project lives in a separate repository.

## Goals / Non-Goals

**Goals:**
- Provide a reproducible benchmark protocol that any evaluator can follow
- Measure the concrete impact of shodh-memory on agent effectiveness across sessions
- Identify specific categories where memory helps most (environment, design decisions, dead ends)
- Diagnose memory system gaps — where memory could have helped but didn't
- Produce shareable documentation (session logs, metrics, comparison reports) suitable for external review
- Cover the full OpenSpec lifecycle: explore → ff/new → apply, all with fresh context per change

**Non-Goals:**
- Benchmarking memory import/export features
- Testing memory concurrency or multi-agent scenarios
- Benchmarking memory performance (latency, storage size)
- Comparing shodh-memory to other memory systems
- Creating the CraftBazaar implementation itself (that happens during benchmark runs)
- Human intervention during agent runs (both runs must be fully autonomous)

## Decisions

### D1: Separate repo for test project, protocol in set-core

**Decision**: The benchmark protocol lives in `benchmark/` within set-core. The CraftBazaar project is a separate git repository created fresh for each benchmark run.

**Why**: The protocol tests set-core features and should be versioned alongside them. The test project needs its own git history, openspec config, and CLAUDE.md — which would conflict if nested in set-core.

**Alternative considered**: Monorepo with `benchmark/craftbazaar/` subdirectory. Rejected because the test project needs its own root-level CLAUDE.md and openspec config.

### D2: Next.js 14 + Prisma + SQLite as test stack

**Decision**: The CraftBazaar project uses Next.js 14 (App Router), Prisma ORM, and SQLite.

**Why**: This stack maximizes natural "trap density" — Prisma has client generation quirks, SQLite has concurrent write issues, and Next.js App Router has server/client component boundaries. All are well-known to Claude but have enough edge cases to create organic mistakes. SQLite means zero external dependencies for reproducibility.

**Alternative considered**: FastAPI + SQLAlchemy (fewer gotchas, less trap potential), Express + Drizzle (less mainstream, harder to evaluate).

### D3: 6 changes with escalating complexity

**Decision**: The benchmark consists of 6 sequential changes, each building on the previous. Changes are designed so early decisions cascade into later ones.

**Why**: 6 changes provide enough surface area for memory to accumulate value (changes 4-6 benefit from changes 1-3), while keeping total runtime practical (~3-4 hours per run). Each change starts with a clean context (`/clear` or new session).

**Change sequence:**
1. Product Catalog with Variants — foundation, variant modeling decision
2. Shopping Cart + Inventory — first encounter with SQLite WAL, variant-as-unit-of-sale
3. Multi-Vendor Order Splitting — THE pivotal design decision (flat vs nested orders)
4. Discount & Coupon Engine — must recall variant scope + vendor model
5. Checkout + Payment (Stripe test mode) — cumulative: env setup + design decisions
6. Order Status Workflow — ultimate payoff: needs correct order architecture from C3

### D4: Two CLAUDE.md variants as the only experimental variable

**Decision**: Run A uses `baseline.md` (no memory hooks, no `set-memory-hooks install`), Run B uses `with-memory.md` (proactive memory enabled + `set-memory-hooks install`). Everything else is identical — same project spec, same change descriptions, same openspec config, same toolchain.

**Why**: Isolating the single variable (memory) makes the comparison valid. The difference operates at two layers: (1) CLAUDE.md proactive memory section (ambient save/recall), and (2) skill-level memory hooks in SKILL.md and command files (recall at skill start, save at skill end). Run A has neither; Run B has both.

### D8: Fully autonomous execution via wt-loop

**Decision**: Both runs execute autonomously via `wt-loop`. No human intervention during execution. The agent self-directs through changes 01-06 by reading change definitions from `docs/benchmark/` inside the project repo, checking `openspec list` for completion status, and picking up the next incomplete change.

**Why**: Human intervention would skew results and make the benchmark non-reproducible. Autonomous execution also enables parallel runs (Run A and Run B simultaneously in separate terminals). The wt-loop provides automatic fresh context per iteration, iteration tracking (time, tokens, commits), and session logs.

**Flow per wt-loop iteration:**
1. Agent reads CLAUDE.md (includes self-directing instructions)
2. Checks `openspec list` to find completed changes
3. Reads next change definition from `docs/benchmark/0N-*.md`
4. Runs `/opsx:ff` → `/opsx:apply` to implement
5. Commits work, writes status to `results/change-0N.json`
6. Session ends → wt-loop restarts with fresh context

### D9: Parallel execution in separate repos

**Decision**: Run A and Run B can execute simultaneously in two separate directories (`~/benchmark/run-a/craftbazaar/` and `~/benchmark/run-b/craftbazaar/`), each with its own git repo, openspec config, and agent. Port collision is avoided by configuring different dev server ports in each CLAUDE.md (PORT=3000 for Run A, PORT=3001 for Run B).

**Why**: Parallel execution halves total benchmark time (~3-4 hours instead of ~6-8). Since each repo is fully independent (separate git, separate SQLite, separate memory store), there is no interference between runs.

### D10: Change file splitting — agent-only vs full

**Decision**: Each change definition in `benchmark/changes/0N-*.md` has two sections: "Agent Input" (task description + acceptance criteria) and "Evaluator Notes" (trap documentation, memory predictions, scoring focus). During bootstrap, only the "Agent Input" sections are extracted into the project repo at `docs/benchmark/0N-*.md`. The agent never sees evaluator notes.

**Why**: If the agent reads trap documentation, it would artificially avoid mistakes, invalidating the benchmark. The splitting ensures the agent works from clean task descriptions while the evaluator has full context for post-run annotation.

**Alternative considered**: Keeping full files in the project and relying on agent instructions to "ignore evaluator notes." Rejected because agents routinely read all available context.

### D5: Automated metrics + post-run manual annotation

**Decision**: Evaluation has two phases. Phase 1 (automatic): wt-loop captures per-iteration metrics (time, tokens, commits, stalls), and the agent writes `results/change-0N.json` status files. Phase 2 (manual): evaluator reviews session transcripts (`.claude/ralph-loop.log`) and annotates with qualitative scores (dead ends, repeated mistakes, design rework).

**Why**: Automated metrics provide the quantitative backbone. Manual annotation adds the qualitative layer that explains *why* metrics differ. The combination provides both rigorous data and compelling narrative. Automatic collection during the run means no data is lost even in fully autonomous execution.

### D6: Diagnostic gap analysis as first-class output

**Decision**: The benchmark includes a diagnostic framework that analyzes not just "did memory help?" but also "where did memory fail to help and why?" Categories include: missed recall opportunities, low-quality saves, missing memory types, timing issues (saved too late), and recall relevance problems.

**Why**: The benchmark's secondary purpose is to improve the memory system itself. Without diagnosing gaps, we only get a pass/fail score without actionable insights.

### D7: Full toolchain bootstrap documented in run guide

**Decision**: The run guide includes exact commands for: `git init`, `openspec init --tools claude`, `wt-deploy-hooks .` (Claude Code hooks), CLAUDE.md placement, and copying agent-only change definitions into `docs/benchmark/`. For Run B additionally: `set-memory-hooks install`. Prerequisites: set-core installed and on PATH, Node.js, Claude Code CLI.

**Why**: Reproducibility requires that any evaluator can set up an identical environment. The bootstrap sequence matters — hooks must be deployed before the first change starts. The run guide must be copy-pasteable end-to-end.

## Risks / Trade-offs

**[Risk: Agent non-determinism]** → The same change may produce different results on different runs even with identical setup. **Mitigation**: Document the model version, run multiple times if resources allow, focus on patterns rather than individual metrics.

**[Risk: Evaluator bias in annotation]** → Manual scoring is subjective. **Mitigation**: Provide detailed rubric with concrete examples for each score level. Include session transcripts so annotations can be verified.

**[Risk: Trap design too artificial]** → If traps are too forced, the benchmark loses credibility. **Mitigation**: Traps are organic consequences of project complexity, not artificial gotchas. The project-spec doesn't mention traps; they emerge naturally from the requirements.

**[Risk: CLAUDE.md differences beyond memory]** → If the with-memory CLAUDE.md accidentally includes other hints, the comparison is invalid. **Mitigation**: Both CLAUDE.md files are version-controlled and reviewable. The only difference is the proactive memory section.

**[Risk: Memory pollution across runs]** → If Run A leaves memories that Run B sees, the comparison is invalid. **Mitigation**: Separate repos with separate SHODH_STORAGE directories. Run A has no memory hooks installed so it never writes to memory. Run B starts with a fresh memory store.

**[Risk: Port collision in parallel runs]** → Both agents running `npm run dev` on the same port. **Mitigation**: CLAUDE.md for each run specifies a different port (PORT=3000 for Run A, PORT=3001 for Run B).

**[Risk: Agent reads evaluator notes]** → If change definition files include trap documentation, agent gains unfair knowledge. **Mitigation**: Bootstrap extracts only "Agent Input" sections into the project repo. Full files with evaluator notes stay in set-core only.

**[Risk: wt-loop stall or infinite loop]** → Agent gets stuck on a change and loops without progress. **Mitigation**: wt-loop has built-in stall detection (configurable `--stall-threshold`). After N iterations with no commits, the loop stops. The evaluator can review and restart if needed — but the stall itself is data (the agent couldn't solve the problem).

## Open Questions

- Should we run the benchmark more than twice (e.g., 3x baseline, 3x with-memory) for statistical significance? **Initial answer**: Start with 1+1, expand if results are ambiguous.
- How many wt-loop iterations to allow? **Initial answer**: `--max 20` (enough for 6 changes + retries, but bounded). With `--stall-threshold 3` to stop unproductive loops.
