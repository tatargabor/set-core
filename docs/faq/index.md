# Frequently Asked Questions

A comprehensive FAQ for architects, CTOs, and senior engineers evaluating SET (ShipExactlyThis) — the autonomous multi-agent orchestration framework for Claude Code.

---

## General

### What is SET?

SET is an orchestration framework that transforms a product specification into fully implemented, tested, and merged code — autonomously. You write a detailed markdown spec (data model, pages, design tokens, auth flows, seed data); SET decomposes it into independent changes, dispatches parallel Claude Code agents into isolated git worktrees, runs deterministic quality gates (build, test, E2E, code review), and merges the results. No babysitting required.

### Who is SET for?

Development teams and technical leaders who already use Claude Code and want to scale beyond single-agent, single-task workflows. If you're an architect managing a backlog of well-specified features, or a CTO evaluating how AI agents can own the full implementation-to-merge cycle, SET is the layer that makes that possible. It assumes you can write a good spec — it handles everything after that.

### Is this production-ready?

SET was built with itself over 79 days (1,295 commits, 134K LOC, 720+ hours of continuous autonomous agent runtime). It has completed 30+ full E2E orchestration runs with published benchmarks: the MiniShop benchmark delivers 6/6 changes merged, zero human intervention, in 1h 45m. CraftBrew (15 changes, 150+ files, 28 DB models) completed fully autonomously in ~6h. These are real projects with real tests passing.

---

## How Is SET Different From...

### ...just using Claude Code?

Claude Code is an excellent single-agent tool. SET is the orchestration layer on top. The difference is like comparing a skilled developer to a managed sprint.

| | Claude Code (alone) | SET |
|---|---|---|
| **Scope** | One task at a time | Full spec → multiple parallel changes |
| **Parallelism** | Agent teams (experimental, ~7 agents, one session) | N worktrees, each with a dedicated agent, across machines |
| **Planning** | Plan mode (freeform, read-only) | OpenSpec: structured artifacts with traceability (proposal → spec → design → tasks) |
| **Quality** | Manual test runs, no enforcement | Automated gate pipeline: dep install → build → test → E2E → code review → smoke |
| **Merging** | Manual `git merge` | Automated merge queue with conflict resolution and post-merge verification |
| **Recovery** | Session dies, you restart manually | Sentinel detects crashes in 30s, auto-restarts, escalates if needed |
| **Memory** | Per-session context | Persistent cross-session memory via hooks (decisions, learnings, conventions survive) |
| **State** | Ephemeral | Atomic JSON state file with full orchestration history |

Claude Code provides the primitives (worktrees, subagents, hooks). SET provides the orchestration: planning, dispatch, monitoring, gating, merging, replanning — the full outer loop.

### ...Claude Code Agent Teams?

Agent Teams (experimental) coordinate multiple Claude instances within a single session with a shared task list. SET orchestrates across sessions, machines, and time:

- **Agent Teams** = parallelism *within* a worktree. A lead assigns subtasks to teammates; they share context and message each other. Good for breaking down a single feature.
- **SET** = parallelism *across* worktrees. A planner decomposes a full spec into a dependency DAG of independent changes, dispatches each to its own worktree with its own agent, and manages the merge pipeline. Good for shipping an entire product.

They're complementary. SET can use Agent Teams inside each worktree for complex individual changes while managing the cross-change orchestration externally.

### ...Cursor's parallel agents?

Cursor 3 introduced parallel agents (up to 8) with worktree isolation. That's significant — it means Cursor now has the *execution* capability. What it lacks is the *orchestration*:

- **No spec decomposition.** Cursor agents are launched from ad-hoc prompts, not from a structured spec with dependency ordering.
- **No quality gates.** No automated build → test → E2E pipeline before merge. If the agent says it's done, it's done.
- **No merge pipeline.** No conflict resolution strategy, no post-merge verification, no cross-worktree sync.
- **No supervision.** No sentinel watching for crashes, stalls, or budget overruns.
- **No persistent state.** No orchestration state file tracking which changes are pending/running/done/merged across restarts.

Cursor gives you 8 agents. SET gives you a *system* that manages those agents toward a verified outcome.

### ...Devin?

Devin is an autonomous AI software engineer — a single agent that takes a task (Jira ticket, bug report) and works on it end-to-end in a sandboxed VM: planning, coding, testing, PR creation.

SET is the orchestration layer that could coordinate *many* Devins (or Claude Code agents) working in parallel on related changes toward the same product spec:

- **Devin** handles one task at a time. SET decomposes a spec into N tasks and runs them in parallel.
- **Devin** creates a PR. SET manages the merge queue with pre-merge quality gates.
- **Devin** has no spec-driven traceability. SET traces every task back to a requirement with WHEN/THEN acceptance criteria.
- **Devin** reports ~67% PR merge rate. SET's MiniShop benchmark: 100% merge rate, zero intervention.

Devin is a worker. SET is the project manager, CI/CD pipeline, and QA team for autonomous workers.

### ...Roo Code (Roo Cline)?

Roo Code organizes AI capabilities into specialized modes (Architect, Code, Debug, Ask) with an Orchestrator that delegates subtasks to the right mode. It's model-agnostic and works in VS Code.

The "multi-agent" in Roo Code is really multi-*mode* within a single session — it's role-based delegation, not parallel execution:

- No worktree isolation (all modes operate on the same workspace).
- No merge pipeline or quality gates.
- No structured spec system — modes are role-based, not requirement-driven.
- No persistent orchestration state.

Roo Code is a sophisticated single-session AI assistant with role specialization. SET is a multi-session, multi-worktree orchestration framework.

### ...Aider?

Aider is a CLI-based AI pair programmer — interactive, lightweight, model-agnostic. It's excellent at what it does: focused code changes with automatic git commits. It has no concept of multi-agent parallelism, spec decomposition, quality gates, or merge orchestration. Aider is a tool you'd use *inside* a worktree; SET is the system that manages the worktrees.

### ...Cline?

Cline is a VS Code extension where every file change and terminal command requires human approval. It's the opposite of autonomous orchestration — deliberate, transparent, human-in-the-loop. SET targets the other end of the spectrum: give it a spec, walk away, come back to merged code. Different philosophies for different trust levels.

### ...Kiro (Amazon)?

Kiro is the closest philosophical match: a spec-driven agentic IDE that generates user stories with acceptance criteria, technical design documents, and implementation task lists from natural language requirements. It shares SET's belief that specs matter more than prompts.

The differences:

- **Kiro** is an IDE. **SET** is a framework that works with your existing tools (Claude Code, git, your editor).
- **Kiro** is single-agent. **SET** runs parallel agents in isolated worktrees.
- **Kiro** generates specs. **SET** also decomposes them into a dependency DAG, dispatches agents, enforces quality gates, manages merges, and replans for gaps.
- **Kiro** has no merge pipeline, sentinel supervision, or crash recovery.

Kiro validates the spec-driven approach. SET takes it further with full orchestration infrastructure.

### ...Windsurf?

Windsurf (by Codeium, acquired by Cognition) is an AI IDE with the Cascade engine for multi-step agentic actions. It has persistent memory across sessions, which is notable. But it's a single-agent IDE experience — no parallel execution, no spec decomposition, no quality gates, no merge pipeline. Windsurf and SET solve different problems at different scales.

### ...OpenHands (OpenDevin)?

OpenHands is an open-source platform for running AI coding agents at scale — potentially thousands of them. It provides the *runtime* (sandboxed environments, model-agnostic agent execution) but not the *orchestration* (spec decomposition, dependency DAG, quality gates, merge pipeline, sentinel supervision). You could build something like SET on top of OpenHands, but OpenHands alone doesn't give you the development workflow.

### ...Composio Agent-Orchestrator?

Composio is architecturally the most similar: parallel agents in worktrees with automated CI fix attempts. The key differences:

- **No spec decomposition.** Composio orchestrates agents but doesn't plan what they should build from a product spec.
- **No pre-merge integration gates.** Relies on CI/CD pipelines after PR creation, not gate enforcement before merge.
- **No persistent orchestration state.** No crash recovery, no resumable state across restarts.
- **No sentinel supervision.**

Composio is an agent runtime with basic coordination. SET is a full development orchestration framework.

### ...GPT-Engineer / Lovable?

Different category entirely. Lovable is an app builder for non-developers — prompt to MVP. SET is infrastructure for professional development teams who write detailed specs and expect production-quality, tested output. Lovable generates apps; SET generates software engineering process outcomes.

---

## OpenSpec

### What is OpenSpec and why not just use a prompt?

OpenSpec is a structured, artifact-driven methodology for specifying and implementing changes. Instead of a conversation or a prompt, work is expressed as a sequence of structured documents (artifacts) that serve as contracts between planner, implementer, and verifier:

1. **Proposal** — Why we're doing this (problem statement, impact)
2. **Specs** — What exactly must be built (requirements with WHEN/THEN acceptance criteria)
3. **Design** — How we'll build it (technical decisions, tradeoffs)
4. **Tasks** — Implementation checklist (each task tagged with `[REQ: requirement-name]` for traceability)

Why not just a prompt?

- **Prompts drift.** Agents interpret, improvise, skip requirements. OpenSpec specs are testable contracts with explicit IN SCOPE / OUT OF SCOPE boundaries.
- **Prompts can't be verified.** How do you check "build a webshop" was done correctly? OpenSpec verification checks every requirement against tasks against code.
- **Prompts don't compose.** When 5 agents work in parallel, a prompt gives no way to divide scope. OpenSpec's delta specs assign specific requirements to specific changes.
- **Prompts leave no record.** After merge, what was the design rationale? OpenSpec archives the full decision chain (proposal → spec → design → tasks) for future reference.

### How is this different from Claude Code's Plan mode?

Plan mode is a *thinking step* — Claude reads the codebase, analyzes the problem, and outlines an approach before implementing. It's freeform, ephemeral, and advisory.

OpenSpec is a *workflow system*:

| | Plan Mode | OpenSpec |
|---|---|---|
| **Output** | Freeform text plan | Structured artifacts (proposal, specs with WHEN/THEN, design, tasks) |
| **Persistence** | Disappears after session | Committed to repo, archived after completion |
| **Traceability** | None | Every task traces to a requirement: `[REQ: auth-login]` |
| **Verification** | None | Automated: completeness (all tasks done?), correctness (spec scenarios covered?), coherence (design followed?) |
| **Scope enforcement** | Trust | Explicit IN SCOPE / OUT OF SCOPE sections |
| **Multi-agent** | Not designed for it | Delta specs assign requirements to specific changes; agents get scoped work |

Plan mode helps a single agent think. OpenSpec gives a system of agents structured contracts to work against and verify.

### What are delta specs?

When a change is created (e.g., `add-user-auth`), its spec files live in `openspec/changes/add-user-auth/specs/`. These are *delta specifications* — the incremental requirements this specific change introduces, using ADDED/MODIFIED/REMOVED/RENAMED markers.

After merge, delta specs sync into *main specs* (`openspec/specs/`) — the single source of truth for each capability. This means:

- Each change only describes what *it* changes, not the entire system.
- Multiple changes can touch the same capability without conflicting at the spec level.
- Main specs evolve incrementally as changes merge.
- The full history is preserved in archived changes.

### What does the artifact workflow look like in practice?

```
/opsx:explore   → Think through the problem (read-only, no artifacts)
/opsx:new       → Create change container, scaffold artifact templates
/opsx:continue  → Create ONE artifact at a time (respects dependency DAG)
/opsx:apply     → Implement tasks from tasks.md
/opsx:verify    → Check completeness, correctness, coherence
/opsx:archive   → Move to archive, sync specs

Or fast-track: /opsx:ff → generates all artifacts in one pass
```

Each artifact depends on the previous: proposal → specs → design → tasks. You can't create tasks before design, because design decisions inform task structure. This is schema-driven — the default `spec-driven` schema enforces this ordering.

---

## Orchestration

### How does parallel execution actually work?

1. **Decompose**: The planner reads your spec, breaks it into independent changes, and creates a dependency DAG (e.g., "data-model" must merge before "product-pages").
2. **Dispatch**: For each change ready to run (dependencies satisfied, under `max_parallel` limit):
   - Create an isolated git worktree branched from main
   - Generate `input.md` with scope, requirements, design context
   - Bootstrap the environment (deps, ports, env files)
   - Start the Ralph Loop (autonomous Claude Code agent iterating until done)
3. **Monitor**: Every 15 seconds, check each agent's status (progress, stall, crash, budget).
4. **Verify**: When an agent reports "done", run the gate pipeline (build → test → E2E → review).
5. **Merge**: Changes passing gates enter the merge queue. Sequential merge with conflict resolution.
6. **Sync**: After each merge, all other running worktrees pull main to stay current.
7. **Replan**: After all planned changes merge, check for uncovered requirements and generate new changes if gaps remain.

### Why git worktrees?

Worktrees provide true filesystem isolation without the overhead of cloning:

- Each agent has its own working directory — no file conflicts during parallel development.
- Each agent has its own branch — git history is clean and independent.
- Worktrees share the same `.git` directory — no disk waste from full clones.
- Agents can independently install deps, run tests, and build without interfering with each other.

This is fundamentally different from agents sharing a workspace and "coordinating" via messages — that approach breaks down when agents edit the same files simultaneously.

### What happens when agents conflict?

Multi-layer conflict resolution:

1. **Preventive**: The dependency DAG orders changes so cross-cutting modifications happen sequentially. Profile-defined `cross_cutting_files()` (e.g., `package.json`, `.env.local`) are serialized.
2. **Generated files**: Lockfiles, `.tsbuildinfo`, build artifacts — auto-resolved with `--ours`, then `pnpm install` regenerates.
3. **Real conflicts**: Source code conflicts cause `merge-blocked` status. The sentinel investigates, may redispatch with retry context, or escalate.
4. **Post-merge sync**: After every merge, all running worktrees pull main immediately. This prevents integration skew.

In practice: CraftBrew (15 parallel changes) had 4 merge conflicts — all auto-resolved. MiniShop (6 changes): zero conflicts.

### What is the sentinel?

An AI supervisor that watches the orchestration and handles what goes wrong. It's a separate agent from the orchestrator — a supervisor/subordinate pattern.

| Event | Sentinel Action |
|---|---|
| Agent crash | Diagnose from logs, restart or escalate |
| Agent stall (>120s no update) | Investigate cause, attempt recovery |
| Periodic checkpoint | Auto-approve (routine) or escalate (unusual) |
| Orchestration complete | Generate summary report |
| Budget overrun | Pause agent, escalate |

Cost: minimal — typically 5-10 LLM calls per entire orchestration run. The sentinel saves hours of wasted compute by catching crashes that would otherwise silently waste an overnight run.

### What is the Ralph Loop?

The autonomous agent cycle running inside each worktree. When dispatched, an agent:

1. Reads the change's `input.md` (orchestrator's brief) and OpenSpec artifacts
2. Creates artifacts if needed (proposal → specs → design → tasks)
3. Implements each task from `tasks.md`
4. Marks tasks complete (`- [ ]` → `- [x]`)
5. Iterates until all tasks done (up to 30 iterations)

The monitor tracks progress via `loop-state.json`, detecting stalls (agent doing the same thing repeatedly) and budget limits.

---

## Quality & Verification

### What are integration gates?

Deterministic quality checks that every change must pass before merging. The key word is *deterministic* — exit codes, not LLM judgment.

| Gate | What it checks | How |
|---|---|---|
| **build** | Code compiles, types check | `tsc --noEmit`, `next build` — exit code 0/1 |
| **test** | Unit/integration tests pass | `vitest run`, `pytest`, `jest --ci` — exit code 0/1 |
| **e2e** | Browser tests pass | `playwright test`, `cypress run` — exit code 0/1 |
| **review** | Code quality, security, patterns | Claude code review — no CRITICAL findings |
| **smoke** | Post-merge sanity | Custom command (e.g., HTTP health check) |
| **spec_coverage** | Requirements addressed | All assigned REQ-IDs have corresponding tasks |

Gates run sequentially (fast gates first for early failure). If a gate fails, the agent receives the error output and retries (up to `max_verify_retries`). No human intervention needed — agents self-heal from test failures, type errors, and build issues.

### Why not just trust the LLM's judgment?

Because LLMs hallucinate confidence. "Looks good to me" from a code review is not the same as `vitest run` returning exit code 0.

In MiniShop's 6 merged changes, there were 5 gate retries — all self-healed:
1. Missing test file → test gate caught it, agent added the file
2. Jest config issue → build gate caught import error, agent fixed path
3. Playwright auth test failures (3x) → agent updated tests to match actual behavior
4. Post-merge type error → agent synced main, resolved mismatch
5. Cart test race condition → agent added `waitForSelector`

An LLM review would have said "looks good" for at least 3 of these. The gates caught real bugs.

### What does verification check?

Three dimensions:

1. **Completeness**: All tasks done? All acceptance criteria met? All requirements traced to implementation?
2. **Correctness**: Do implementations match spec requirements? Are WHEN/THEN scenarios covered?
3. **Coherence**: Do code changes follow design decisions? Any scope overshoot? Pattern consistency?

Output: detailed report with traceability matrix, issues categorized as CRITICAL/WARNING/SUGGESTION, and a final PASS/FAIL verdict.

### How do you measure output quality across runs?

Structural convergence. Run the same spec twice independently and measure how similar the outputs are:

- **MiniShop**: 83% structural convergence (same routes, schemas, component hierarchy)
- **Micro-Web**: 87% convergence
- **Both**: 100% schema equivalence, 100% convention compliance

Remaining divergence is stylistic (variable naming, CSS order), not structural. The spec + template system produces deterministic architecture even with non-deterministic LLMs.

---

## Memory & Learning

### How does persistent memory work?

SET uses a hook-driven memory system (shodh-memory) that captures and injects context automatically — agents don't need to explicitly save anything.

| Hook | When | What |
|---|---|---|
| **Warmstart** | Session start | Loads relevant memories as context |
| **Pre-tool** | Before each tool call | Injects topic-based recall |
| **Post-tool** | After Read/Bash | Surfaces past experience with similar files/errors |
| **Save** | Session end | Extracts and saves new insights from conversation |

Memory types: Decision (architectural choices), Learning (discovered patterns), Context (project state), Bug (known issues + fixes), Feedback (user preferences).

### Why does memory matter for orchestration?

Without memory, every agent rediscovers the same conventions, makes the same mistakes, and wastes tokens on the same investigations. Benchmarks show:

- **-20% token usage** via memory avoiding re-discovery
- **+34% convention compliance** (agents follow established patterns instead of inventing new ones)
- **Zero voluntary saves** across 15+ sessions — agents don't save on their own. The hook infrastructure is essential.

Learnings from failed runs convert to rules, which are enforced in the next run. The system improves with every orchestration.

---

## Architecture & Extensibility

### What is the plugin system?

SET separates abstract orchestration (Layer 1: `lib/set_orch/`) from project-specific knowledge (Layer 2: `modules/`).

- **Layer 1 (Core)**: Dispatcher, monitor, merger, gates, profiles — no project-specific logic. Works for any project type.
- **Layer 2 (Modules)**: `modules/web/` knows about Next.js, Playwright, Prisma. `modules/example/` is the reference plugin (Dungeon Builder game).
- **Layer 3 (External plugins)**: Your own project type in a separate repo. `pip install` + `entry_points` registration. Takes priority over built-in modules.

Each module implements the `ProjectType` ABC: `detect_test_command()`, `detect_e2e_command()`, `get_forbidden_patterns()`, `get_verification_rules()`, custom gates, merge strategies, planning rules. This means a `set-project-fintech` plugin could add IDOR scanning, PCI compliance checks, and financial calculation verification — all as gates in the merge pipeline.

### Can I use this without Claude Code?

No. SET is built specifically for Claude Code and goes deeper into its capabilities (worktrees, hooks, MCP, skills, subagents). This is by design — SET doesn't abstract over LLMs. It leverages Claude's strengths (long context, tool use, code understanding) fully.

### Can this run on-premise?

The infrastructure is designed for it. SET is self-hosted — no SaaS dependency. When on-premise Claude models become available for regulated industries (banks, defense, government), SET's architecture works unchanged. The orchestration engine, gates, and state management have no cloud dependency. Only the LLM inference endpoint needs to be configured.

### How does design system integration work?

SET can integrate design tokens and visual specifications:

1. **Export from design tool** → `design-system.md` (tokens: colors, fonts, spacing) + `design-brief.md` (per-page visual descriptions)
2. **Dispatcher scope-matches** relevant pages to each change → per-change `design.md`
3. **Agent receives** exact hex colors, font names, component layouts
4. **Review gate checks** design compliance — token mismatches are flagged

This eliminates the "shadcn defaults everywhere" problem. Agents implement *your* brand, not a generic component library.

---

## Practical

### What does a spec need to contain?

Your spec is the single most important input. The orchestration is only as good as the specification. Required sections:

1. **Project overview** — What is this? Who is it for? Tech stack?
2. **Data model** — Entities, fields, relationships (becomes Prisma schema)
3. **Page layouts** — Structure of each page (sections, columns, components)
4. **Component behavior** — Interactive elements (click, hover, state changes)
5. **Auth & roles** — Who can do what? Protected routes?
6. **Seed data** — Initial data with realistic values (not "Product 1")
7. **Design tokens** — Brand colors (hex), fonts, spacing
8. **E2E test expectations** — Critical flows to test

Each requirement needs a **REQ-ID** (`REQ-AUTH-01`) and at least one **WHEN/THEN scenario**. This enables automated spec coverage tracking and verification.

### How long does an orchestration take?

Depends on spec complexity:

| Project | Changes | Wall time | Tokens | Human interventions |
|---|---|---|---|---|
| **Micro-Web** (simple) | 3-4 | ~45m | ~1M | 0 |
| **MiniShop** (e-commerce) | 6 | 1h 45m | 2.7M | 0 |
| **CraftBrew** (complex app) | 15 | ~6h | ~11M | 0 |

Token scaling is super-linear (4x tokens for 2.5x changes) because later changes require more context from merged code.

### What are the self-healing capabilities?

When a gate fails, the agent receives the error output and retries automatically:

- **Test failure**: Agent reads the test error, fixes the code or test, reruns
- **Build error**: Agent reads the type/compilation error, fixes it
- **E2E failure**: Agent sees the Playwright trace, updates selectors or waits
- **Post-merge type mismatch**: Agent syncs main, resolves conflicts

Sentinel-level recovery:
- **Agent crash**: Sentinel detects dead PID within 30s, restarts
- **Agent stall**: Watchdog detects identical action hashes, escalates (warn → restart → redispatch → fail)
- **Orphaned worktree**: Cleaned up on restart

### How do I get started?

```bash
# Install SET
pip install -e .
pip install -e modules/web

# Initialize a project
set-project init --name my-app --project-type web --template nextjs

# Write your spec (docs/spec.md)

# Start orchestration via manager
curl -X POST http://localhost:7400/api/my-app/sentinel/start \
  -H 'Content-Type: application/json' \
  -d '{"spec":"docs/spec.md"}'
```

Or use the step-by-step approach:
```
/opsx:explore   → Think through the problem
/opsx:ff mychange → Generate all artifacts
/opsx:apply     → Implement
/opsx:verify    → Check
/opsx:archive   → Done
```

See the [Quick Start guide](guide/quick-start.md) for the full walkthrough.

---

## The Big Picture

### What problem does SET actually solve?

The gap between "AI can write code" and "AI can ship software." Writing code is 20% of the work. The other 80% is: decomposing requirements, coordinating parallel work, handling conflicts, running quality checks, managing merge order, recovering from failures, and learning from mistakes. SET automates the 80%.

### Why specs instead of prompts?

Because "build a webshop" produces a different webshop every time. "Build a webshop with these 28 data models, these 12 pages with this layout, these design tokens, these auth rules, these seed data records, and these E2E test scenarios" produces the same webshop every time. The spec is the determinism layer that makes LLM output reproducible.

MiniShop achieves 83% structural convergence across independent runs from the same spec. Without specs, convergence approaches 0%.

### How is this different from just running CI/CD?

CI/CD validates code *after* a human (or AI) creates a PR. SET manages the entire pipeline *before* the PR exists:

- **CI/CD**: PR created → tests run → review → merge
- **SET**: Spec written → decomposed → agents dispatched → gates enforced → merge managed → gaps replanned

CI/CD assumes someone creates the PR. SET creates the PRs, validates them, merges them, and identifies what's still missing.

### Why not abstract over multiple LLMs?

Because depth beats breadth. SET leverages Claude-specific capabilities: 200K+ context for large codebases, native tool use for file operations, worktree support for isolation, hooks for memory injection, MCP for external integrations. Abstracting to a lowest-common-denominator API would sacrifice these capabilities for theoretical portability. SET bets on Claude getting better — and compounds that bet.

### What's the competitive moat?

The combination. No other tool provides *all six*:

1. **Structured specs** with traceable requirements
2. **Parallel agents** in isolated worktrees
3. **Deterministic quality gates** (exit codes, not vibes)
4. **Automated merge pipeline** with conflict resolution
5. **Sentinel supervision** with crash recovery
6. **Persistent memory** that improves across runs

Most tools have 1-2 of these. The closest competitors (Composio, Kiro, Augment) have 2-3. The value is in the integration — the six capabilities reinforce each other. Structured specs enable meaningful gates. Gates enable autonomous merging. Memory enables learning. The sentinel enables unattended operation. None works as well alone.
