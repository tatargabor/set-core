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

Claude Code in 2026 is dramatically capable on its own: native worktrees (`--worktree`), Agent Teams (experimental, 3-5 agents with worktree isolation), 27 hook events, auto-memory (`MEMORY.md`), Plan mode, subagents, the Agent SDK, and MCP support. SET is built *on top of* all these primitives — it provides the opinionated orchestration workflow that ties them together.

| | Claude Code (alone) | SET |
|---|---|---|
| **Scope** | One task or one team session | Full spec → decomposed into N parallel changes |
| **Planning** | Plan mode (freeform, ephemeral, read-only) | OpenSpec: persistent versioned artifacts (proposal → spec → design → tasks) |
| **Quality** | Hooks *can* run checks, but you wire them yourself | Structured gate pipeline: dep install → build → test → E2E → review → smoke |
| **Merging** | Manual `git merge`, no enforcement | Automated merge queue with integration gates, conflict resolution, post-merge verification |
| **Recovery** | Session dies, you restart manually | Sentinel detects crashes in 30s, auto-restarts, graduated escalation |
| **Memory** | Auto-memory (flat file loaded at startup) | Semantic memory graph with topic-based recall, auto-injection at every lifecycle point |
| **State** | Session-scoped, lost on restart | Atomic JSON state file with full orchestration history, resumable across restarts |
| **Coordination** | Agent Teams: shared task list + mailbox (one session) | Cross-session, cross-machine orchestration with sentinel supervisor |

Claude Code gives you excellent building blocks. SET gives you the assembled machine: planning, dispatch, monitoring, gating, merging, replanning — the full outer loop. You *could* build this yourself using the Agent SDK and hooks — SET is the battle-tested implementation.

**What SET doesn't have that Claude Code does natively:** Claude Code's 101+ plugin marketplace, the Agent SDK for custom agent development, and deep IDE integration (VS Code, JetBrains). SET is CLI-first with a web dashboard, not an IDE experience.

### ...Claude Code Agent Teams?

Agent Teams (experimental) coordinate multiple Claude instances within a single session with a shared task list and inter-agent messaging. Each teammate can work in its own worktree via `isolation: worktree`. 3-5 teammates recommended, no hard limit.

- **Agent Teams** = parallelism *within* one session. A lead assigns subtasks; teammates share context and message each other. Good for breaking down a single feature. Still experimental: no session resumption for teammates, task status can lag, shutdown can be slow, one team per session.
- **SET** = parallelism *across* sessions, machines, and time. A planner decomposes a full spec into a dependency DAG of independent changes, dispatches each to its own worktree with its own long-running agent, runs quality gates before merge, and manages the merge pipeline. Good for shipping an entire product.

They're complementary. SET can use Agent Teams inside each worktree for complex individual changes while managing the cross-change orchestration externally.

**What Agent Teams does better:** Zero-setup parallelism within a session. No framework installation, no orchestration config. Start a team with one environment variable. For a quick parallel task within a single feature, Agent Teams is faster to reach for.

### ...Cursor's parallel agents?

Cursor introduced Background Agents (BGA): cloud-hosted VMs that work autonomously, create branches, and open PRs. Each BGA gets its own sandboxed environment.

What Cursor has:
- **Cloud execution** — agents run in Cursor's cloud, no local resources needed. You can close your laptop.
- **Git branch + PR workflow** — each BGA creates a branch and opens a PR when done.
- **Cursor Rules** (`.cursor/rules/`) — static text instructions scoped by glob pattern to constrain agent behavior.
- **GitHub Issue triggers** — link an issue to a BGA.

What Cursor lacks vs SET:
- **No spec decomposition.** BGAs are launched from ad-hoc prompts or issues, not from a structured spec with dependency ordering.
- **No quality gates before merge.** If the agent says it's done, it opens a PR. No automated build → test → E2E pipeline before the PR exists. It relies on your CI.
- **No inter-agent coordination.** Multiple BGAs working on the same repo have no awareness of each other. No merge conflict prevention, no merge ordering.
- **No persistent orchestration state.** No tracking of which changes are pending/running/done/merged across restarts.
- **No sentinel supervision.** No crash recovery or stall detection.

**What Cursor does better:** Cloud execution (no local resource cost), GitHub-native workflow (issue → PR), lower barrier to entry (it's an IDE with built-in agents), and Cursor Rules are simpler to write than SET's orchestration config. For small, independent tasks, Cursor BGA is arguably easier to use.

### ...Devin?

Devin (by Cognition) is an autonomous AI software engineer — takes a task and works end-to-end in a sandboxed VM: planning, coding, testing, PR creation. Can run multiple concurrent sessions, each in its own VM.

| | Devin | SET |
|---|---|---|
| **Execution** | Cloud VM sandbox | Local worktrees |
| **Parallelism** | Multiple independent sessions (no coordination) | Coordinated parallel via orchestrator + merge queue |
| **Planning** | Informal step-by-step (visible in UI) | OpenSpec: structured artifacts with traceability |
| **Testing** | Runs tests if they exist (ad-hoc) | Structured gate pipeline (build → test → E2E → review) |
| **Self-review** | Basic re-read (inconsistent) | Separate verification phase with code review gate |
| **Integrations** | Excellent Slack/Jira/GitHub (trigger via Slack message) | CLI + web dashboard + MCP |
| **Merge safety** | Opens PR, relies on CI | Integration gates enforced before merge |
| **Recovery** | Within-session retry | Sentinel: crash detection, stall recovery, redispatch |

**What Devin does better:** Slack integration is best-in-class — assign a task from Slack, get a PR back. The sandboxed VM means zero local setup. The UI for watching agent work is polished. For well-scoped, independent tasks (migrations, CRUD endpoints, test writing), Devin's workflow is smoother than setting up SET orchestration.

**What SET does better:** Multi-change coordination, spec-driven traceability, quality gates before merge (not after), sentinel supervision, persistent memory, and deterministic merge ordering. SET is for shipping a product from spec; Devin is for delegating individual tasks.

### ...Kiro (Amazon)?

Kiro is the closest philosophical match: a spec-driven agentic IDE that generates user stories with acceptance criteria, design documents, and implementation task lists. Built on VS Code, powered by Amazon Bedrock (Claude).

Kiro's genuine innovations:
- **Spec flow is the best in-IDE implementation.** User Story → Design Doc → Task List, all in a guided wizard within the IDE. Specs stored as markdown in `.kiro/specs/`.
- **Hooks are novel.** Event-driven automated actions that trigger on file events (e.g., file save triggers README update, schema change triggers type regeneration). Defined in `.kiro/hooks/`.
- **Steering files** (`.kiro/steering/`) — clean project-level instruction system.
- **Free tier + VS Code familiarity** — zero barrier to entry.

| | Kiro | SET |
|---|---|---|
| **Spec system** | In-IDE wizard, generated specs | CLI-driven OpenSpec, manual + automated |
| **Agent scope** | Single-session, IDE-bound | Daemon-based, hours-long autonomous runs |
| **Parallel agents** | None (single agent per IDE) | Worktree-based, N parallel agents |
| **Quality gates** | Hooks + spec adherence | Full pipeline: build → test → E2E → review |
| **Merge handling** | Basic git | Integration-gated merge queue |
| **Memory** | Steering files (static) | Semantic memory with cross-session learning |
| **Design integration** | None | Design pipeline (tokens, briefs, per-change design.md) |

**What Kiro does better:** Lower barrier to entry — no CLI setup, no orchestration concepts, just open the IDE and follow the wizard. The hooks system (file-event triggers) is something SET doesn't have at the IDE level. Spec generation from natural language is guided and approachable. For a single developer who wants structured AI assistance without a framework, Kiro is easier.

**What SET does better:** Everything after spec creation — decomposition, parallel execution, quality enforcement, merge automation, supervision, cross-session learning.

### ...Roo Code (Roo Cline)?

Roo Code organizes AI capabilities into configurable modes (Architect, Code, Debug, Ask, custom) with a "Boomerang" pattern where an Orchestrator mode delegates subtasks to specialized modes. Model-agnostic.

The "multi-agent" is really multi-*mode* within a single session — sequential delegation, not parallel execution:
- No worktree isolation (all modes operate on the same workspace).
- No merge pipeline or quality gates.
- No structured spec system.
- No persistent orchestration state or cross-session memory (manual rules files only).

**What Roo Code does better:** Extremely easy to set up. Custom modes are intuitive — define a persona with tools and permissions, no code needed. Model-agnostic — use any LLM provider. Fully open source with an active community. For individual developers who want flexible AI assistance without framework overhead, Roo Code is lighter and more accessible.

### ...Aider?

Aider is a CLI-based AI pair programmer — interactive, lightweight, model-agnostic. Single-agent, single-session. No parallelism, no spec decomposition, no quality gates, no merge orchestration.

**What Aider does genuinely better than SET (and most alternatives):**
- **Git integration** — best-in-class. Every edit auto-committed with meaningful messages. Full undo via `git revert`. No other tool matches this.
- **Model flexibility** — supports virtually every LLM provider. Easy mid-session model switching. SET is Claude-only.
- **Repo map** — tree-sitter-based symbol map gives the LLM structural codebase awareness efficiently. Smart context management.
- **Cost efficiency** — careful token usage, transparent cost tracking per message.
- **Edit format innovation** — matches diff format to model capability (diff, whole-file, udiff). Genuine innovation.

Aider is a tool you'd use *inside* a worktree; SET is the system that manages the worktrees. Complementary, not competitive.

### ...Cline?

Cline is a VS Code extension where every action is transparent and controllable. Has an auto-approve mode but fundamentally designed for human oversight.

**What Cline does better:**
- **MCP marketplace** — best-in-class. MCP server discovery, installation, and configuration directly in the extension. The largest MCP ecosystem.
- **Transparency** — shows every tool call, diff, and command. You see exactly what the agent does and why.
- **Model flexibility** — any LLM provider (OpenAI, Anthropic, local models, custom endpoints).
- **Open source** — fully open, active community, rapid iteration.

Different philosophy: Cline is deliberate, transparent, human-in-the-loop. SET is autonomous, hands-off, spec-driven. For developers who want to understand and approve every change, Cline is the right tool.

### ...GitHub Copilot Coding Agent?

Copilot Coding Agent is GitHub's background AI — assign a GitHub Issue to Copilot, it creates a branch, makes changes, runs your CI (GitHub Actions), self-reviews, and opens a PR. Runs in GitHub-hosted cloud environments.

| | Copilot Coding Agent | SET |
|---|---|---|
| **Trigger** | GitHub Issue assignment | Spec document |
| **Execution** | Cloud (GitHub-hosted) | Local worktrees |
| **Quality** | Runs existing CI + self-review | Structured gate pipeline before merge |
| **Parallelism** | Multiple independent agents (no coordination) | Coordinated parallel with dependency DAG |
| **Merge** | Opens PR, human reviews | Automated merge queue with integration gates |
| **Distribution** | GitHub-native (largest distribution) | Framework installation needed |

**What Copilot does better:** Zero setup for GitHub users — it's built in. GitHub-native workflow (Issue → PR). Cloud execution. The largest distribution of any AI coding agent. For well-scoped, independent issues, it's the lowest-friction option.

**What SET does better:** Coordinated multi-change development from a single spec. Copilot handles one issue → one PR with no awareness of other agents on the same repo. SET manages the dependencies, merge ordering, conflict resolution, and spec coverage tracking.

### ...Windsurf?

Windsurf (by Codeium) was an AI IDE with the Cascade engine for multi-step agentic actions with strong context tracking across files and terminal commands. OpenAI announced acquisition of Codeium for ~$3B (late 2024). Current product status post-acquisition is uncertain.

Single-agent IDE experience — no parallel execution, no spec decomposition, no quality gates, no merge pipeline. Cascade's context tracking within a session was genuinely strong, and autocomplete was fast.

### ...OpenHands (OpenDevin)?

OpenHands is the strongest open-source single-agent coding runtime — Docker-sandboxed, multi-model, strong SWE-bench results (50%+). It provides the *runtime* (execute code, browse web, edit files in a sandbox) but not the *orchestration* (spec decomposition, parallel coordination, quality gates, merge pipeline, sentinel).

You could theoretically build a SET-like orchestrator on top of OpenHands as the agent runtime. OpenHands alone is a worker, not a coordinator.

### ...Composio?

**Correction from earlier versions of this FAQ:** Composio is primarily a **tool-integration platform** (250+ pre-built API integrations for AI agents), not an agent orchestrator. It provides middleware for frameworks like CrewAI, LangGraph, and AutoGen to call external tools (GitHub, Jira, Slack, databases) via function calling. It has a reference SWE-agent implementation but no parallel orchestration, quality gates, or merge pipelines. Different category from SET.

### ...GPT-Engineer / Lovable?

Different category entirely. Lovable is an app builder for non-developers — prompt to MVP. SET is infrastructure for professional development teams who write detailed specs and expect production-quality, tested output. Lovable generates apps; SET generates software engineering process outcomes.

---

### Capability matrix: SET vs. the landscape

| Tool | Parallel Agents | Worktree Isolation | Structured Specs | Quality Gates | Merge Pipeline | Supervisor | Cloud Exec | Model Flexibility |
|---|---|---|---|---|---|---|---|---|
| **SET** | Yes | Yes | Yes (OpenSpec) | Yes (7 gates) | Yes | Yes (Sentinel) | No (local) | Claude only |
| Claude Code | Experimental (Teams) | Yes (native) | No | Hooks (DIY) | No | No | No | Claude only |
| Cursor BGA | Yes (cloud VMs) | Branches (cloud) | No | No (relies on CI) | No | No | Yes | Multi-model |
| Devin | Independent sessions | Sandbox VMs | No | Ad-hoc (runs tests) | No | No | Yes | Proprietary |
| Kiro | No | No | Yes (in-IDE) | Hooks (file events) | No | No | No | Claude (Bedrock) |
| Copilot Agent | Independent agents | Cloud VMs | No | CI + self-review | No | No | Yes | GPT/Claude |
| Roo Code | No (modes) | No | No | No | No | No | No | Any LLM |
| Aider | No | No | No | No | No | No | No | Any LLM |
| Cline | No | No | No | No | No | No | No | Any LLM |
| OpenHands | No | Docker sandbox | No | No | No | No | Yes | Any LLM |

**What SET uniquely provides:** The combination of all six in the left columns. Other tools excel in areas SET doesn't cover: cloud execution (Cursor, Devin, Copilot), model flexibility (Aider, Roo Code, Cline), IDE integration (Kiro, Cursor, Windsurf), and zero-setup simplicity (Copilot, Cline).

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

Plan mode is a *thinking step* — Claude reads the codebase, analyzes the problem, and outlines an approach before implementing. It's freeform, ephemeral (exists within the session only), and advisory. Plans are not saved to disk as separate artifacts — when you accept a plan, Claude proceeds to implement. Ctrl+G opens the plan in your editor for manual editing.

OpenSpec is a *workflow system*:

| | Plan Mode | OpenSpec |
|---|---|---|
| **Output** | Freeform text plan | Structured artifacts (proposal, specs with WHEN/THEN, design, tasks) |
| **Persistence** | Session-scoped (lost when session ends) | Committed to repo, archived after completion |
| **Traceability** | None | Every task traces to a requirement: `[REQ: auth-login]` |
| **Verification** | None | Automated: completeness (all tasks done?), correctness (spec scenarios covered?), coherence (design followed?) |
| **Scope enforcement** | Trust | Explicit IN SCOPE / OUT OF SCOPE sections |
| **Multi-agent** | Not designed for it | Delta specs assign requirements to specific changes; agents get scoped work |

Plan mode helps a single agent think. OpenSpec gives a system of agents structured contracts to work against and verify.

### How is this different from Kiro's spec system?

Kiro also generates specs — user stories with acceptance criteria, design documents, and task lists. It's the closest approach to OpenSpec in the market. The differences:

- **Generation vs. orchestration.** Kiro generates specs within one IDE session for one agent to implement. OpenSpec generates specs AND decomposes them into a dependency DAG for parallel multi-agent execution.
- **Persistence model.** Kiro specs live in `.kiro/specs/` and are consumed within the IDE. OpenSpec specs are versioned artifacts that sync across worktrees, survive archiving, and build a living specification library (363 specs in set-core itself).
- **Delta specs.** OpenSpec has a unique concept: each change creates *delta specifications* (incremental ADDED/MODIFIED/REMOVED requirements) that sync into main specs after merge. Multiple changes can touch the same capability without conflicting.
- **Verification.** OpenSpec has automated verification (completeness, correctness, coherence) with traceability matrices. Kiro's quality enforcement is through file-event hooks, not spec-level verification.

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

### Why git worktrees instead of cloud VMs?

Worktrees provide true filesystem isolation without the overhead of cloud infrastructure:

- Each agent has its own working directory — no file conflicts during parallel development.
- Each agent has its own branch — git history is clean and independent.
- Worktrees share the same `.git` directory — no disk waste from full clones.
- Agents can independently install deps, run tests, and build without interfering with each other.
- Everything runs locally — no cloud costs, no network latency, full control.

This is fundamentally different from agents sharing a workspace and "coordinating" via messages — that approach breaks down when agents edit the same files simultaneously.

**Trade-off vs. cloud VMs (Cursor BGA, Devin, Copilot):** Cloud agents can run without your machine being on. SET requires a running machine. For overnight runs this matters — SET needs an always-on server or workstation.

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

### How is this different from just running CI after a PR?

CI/CD validates code *after* a PR exists. SET's gates run *before* merge — the agent receives gate failures and self-heals before the code ever reaches main. This is the difference:

- **Copilot/Devin/Cursor:** Agent creates PR → CI runs → CI fails → human notices → human tells agent to fix → repeat.
- **SET:** Agent reports "done" → gate runs → gate fails → agent receives error → agent fixes → gate re-runs → passes → merge.

The feedback loop is automated and internal. No human in the loop for routine failures.

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

### How is this different from Claude Code's auto-memory?

Claude Code has native auto-memory since v2.1.59: Claude saves notes to `~/.claude/projects/<project>/memory/MEMORY.md` and topic files. The first 200 lines are loaded at session start. Shared across worktrees of the same repo.

SET's shodh-memory goes further:
- **Semantic recall** — topic-based queries, not just flat file loading. "What do we know about Prisma migrations?" returns relevant memories, not everything.
- **Lifecycle injection** — memory is injected at 4 points (warmstart, pre-tool, post-tool, save), not just at session start.
- **Automatic extraction** — session-end hooks extract decisions, learnings, and bugs from the conversation without explicit save.
- **Memory graph** — tags, relationships, deduplication, consolidation. Not just a flat list.
- **MCP tools** — programmatic memory operations (remember, recall, forget, brain, context_summary) available as tools during sessions.

Claude Code's auto-memory is a notebook. SET's memory is a queryable knowledge base.

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

**This is a deliberate trade-off.** Tools like Aider, Roo Code, and Cline support any LLM provider. SET bets on Claude getting better and compounds that bet. If you need model flexibility, SET is not the right choice.

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

## What SET Doesn't Do (Yet)

Honest gaps where competitors are ahead — these inform our development roadmap:

| Gap | Who does it better | Notes |
|---|---|---|
| **Cloud execution** | Cursor BGA, Devin, Copilot | SET requires a running local machine. Cloud agents work while you sleep. |
| **Model flexibility** | Aider, Roo Code, Cline | SET is Claude-only by design. No GPT, Gemini, or local model support. |
| **IDE integration** | Kiro, Cursor, Windsurf | SET is CLI + web dashboard. No VS Code/JetBrains plugin for in-editor orchestration control. |
| **Zero-setup simplicity** | Copilot, Cline, Cursor | SET requires pip install, project init, orchestration config. Others are install-and-go. |
| **GitHub Issue → PR** | Copilot Coding Agent | SET works from specs, not from issue trackers. No native Jira/Linear/GitHub Issue integration. |
| **Slack integration** | Devin | Can't trigger SET orchestration from Slack. |
| **File-event hooks** | Kiro | SET's hooks are at the orchestration level, not IDE file-save events. |
| **MCP marketplace** | Cline | SET has a custom MCP server, but no marketplace for discovering third-party integrations. |

These are conscious trade-offs, not oversights. SET optimizes for orchestration depth over integration breadth. Some may become development priorities as the framework matures.

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

This is a trade-off. If Claude Code changes its API or another model becomes dramatically better, SET's Claude-only approach becomes a liability. We accept this risk for the depth advantage.

### What's the competitive moat?

The combination. No other tool provides *all six*:

1. **Structured specs** with traceable requirements
2. **Parallel agents** in isolated worktrees
3. **Deterministic quality gates** (exit codes, not vibes)
4. **Automated merge pipeline** with conflict resolution
5. **Sentinel supervision** with crash recovery
6. **Persistent memory** that improves across runs

Most tools have 1-2 of these. The closest competitors (Kiro for specs, Cursor for parallel agents, Copilot for cloud execution) have 2-3 each. The value is in the integration — the six capabilities reinforce each other. Structured specs enable meaningful gates. Gates enable autonomous merging. Memory enables learning. The sentinel enables unattended operation.

The moat is not any single feature — it's the assembled system and the 30+ production runs of battle-testing that validate it works together.
