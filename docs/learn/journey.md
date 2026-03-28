[< Back to Index](../INDEX.md)

# Development Journey

**1,295 commits · 329 archived changes · 363 specs · 79 days**

set-core was built with set-core. Every feature was planned through OpenSpec, implemented by agents, and validated through quality gates. The framework bootstrapped itself — by Phase 5, the orchestration engine was building its own next features.

## By The Numbers

| Metric | Value |
|--------|-------|
| Development | 950+ hours across 79 days (Jan 9 -- Mar 28, 2026) |
| Commits | 1,295 (~16/day) |
| Capability specifications | 363 |
| Archived OpenSpec changes | 329 |
| Total codebase | 134K LOC |
| -- Python (engine, GUI, modules) | 59,000 |
| -- Shell scripts (CLI tools) | 15,000 |
| -- TypeScript (dashboard) | 14,000 |
| -- OpenSpec specs | 23,000 |
| -- Docs + templates + rules | 22,000 |
| Autonomous agent runtime | 720+ hours (~60 days x 12h/day continuous) |
| Best benchmark | CraftBrew run #7: 14/14 merged (100%) |

## Development Timeline

### Phase 1: Worktree Tools (Jan 9--24)

The project began as **wt-tools** — bash CLI scripts for managing parallel Claude Code agents via git worktrees. The first scripts were simple: `wt-new` to create a worktree, `wt-work` to open it in an editor, `wt-list` to show all active branches, `wt-close` to clean up, and `wt-merge` to bring work back to main. JIRA integration followed quickly — agents needed ticket context. File activity tracking and multi-machine worklog support made it possible to run agents on multiple machines against the same repo.

By the end of this phase, a developer could spin up 5 parallel agents, each in its own worktree, each working on a different ticket — but they still had to manage all of it manually from the terminal.

**Key insight:** Git worktrees are the natural unit of parallel AI agent work — real branches, real isolation, real merges. No Docker containers, no virtual environments, just git.

### Phase 2: GUI Control Center + Team Sync (Jan 24--29)

30+ changes in one week. The PyQt-based Control Center replaced the terminal workflow with a visual worktree table showing status indicators (idle, running, done, error), running animations for active agents, and right-click context menus for common operations. Team sync added multi-agent messaging so agents could coordinate without human relay. Multi-editor support (VS Code, Zed, Cursor) meant agents could launch in whatever IDE the developer preferred.

This was the most intense burst of development — the GUI went from nothing to a fully functional control center in five days because every feature was a separate OpenSpec change running in parallel.

**Key insight:** Developers need visual feedback when managing multiple parallel agents. CLI-only doesn't scale past 3 concurrent agents.

### Phase 3: Memory Integration (Feb 11--17)

Integrated [shodh-memory](https://github.com/nicholasgasior/shodh) across the entire workflow. The GUI gained a memory browser with search and tagging. OpenSpec lifecycle hooks saved context at every stage — when a change was created, when artifacts were generated, when verification passed or failed. Proactive mid-flow recall injected relevant past experience into agent sessions.

The hardest bug: RocksDB lock contention causing silent data loss when multiple agents wrote memories simultaneously. Fixed with a write queue and retry logic.

Built the CraftBazaar benchmark — a synthetic test protocol measuring memory effectiveness across repeated runs. Six benchmark runs achieved **+34% weighted improvement** with memory enabled vs. without.

**Key insight:** Agents don't save memories voluntarily — zero saves observed across 15+ sessions. They're too focused on the immediate task. Infrastructure must handle it via hooks.

### Phase 4: Ralph Loop + Autonomous Agents (Feb 15--19)

Single-shot agent prompts fail on complex tasks. An agent told to "implement the cart feature" would get 70% done and stop. The Ralph Loop changed this: autonomous agent iterations with stall detection (has the agent stopped making progress?), done criteria (are all tasks checked off?), and per-change iteration tracking. Named after a relentless factory worker who never stops until the job is done.

The 5-layer hook architecture emerged from repeated agent failures: frustration detection (agent is going in circles), commit-save (checkpoint work before potential crash), transcript extraction (learn from what happened), branch-aware tagging (which worktree did this happen in?), and lifecycle events (start, pause, resume, done).

**Key insight:** Single-shot agent prompts fail on complex tasks. Iterative loops with trend detection and auto-pause are the reliable pattern.

### Phase 5: Orchestration Engine (Feb 25--27)

The architectural leap. **set-orchestrate** accepts a product spec (plain markdown), decomposes it via LLM into a dependency DAG of changes, dispatches each change to a parallel worktree agent, monitors progress, and auto-replans when things go wrong. Token budgets prevent runaway agents. Time limits catch infinite loops. The audit system records every decision for post-run analysis.

This was the inflection point: the system went from "tool that helps developers manage agents" to "autonomous framework that builds projects from specs." The first successful end-to-end run built a working Next.js app from a 2-page product spec with zero human intervention.

**Key insight:** The transition from "tool that helps developers" to "autonomous framework that builds projects from specs" was a single architectural leap — the decompose-dispatch-monitor loop.

### Phase 6: Sentinel + Merge Pipeline (Mar 2--8)

The orchestrator was powerful but fragile. It would crash at 2 AM and the entire run was wasted. The sentinel supervisor fixed this: non-blocking polls every 30 seconds, crash diagnosis via log analysis, automatic restart with state recovery.

The merge pipeline went through three iterations. First attempt: parallel merges (disaster — cascading conflicts). Second attempt: sequential queue with ff-only merge (better, but post-merge smoke tests caught integration bugs too late). Final design: sequential queue with integrate-then-verify — merge main into the branch first, run all gates, then fast-forward merge into main.

Decomposed the monolithic 2000-line orchestrator into 7 library modules (`dispatcher.py`, `monitor.py`, `merger.py`, `verifier.py`, `planner.py`, `digest.py`, `events.py`). Built the events system for inter-module communication. Created the MiniShop E2E test scaffold — the first reproducible benchmark.

**Key insight:** Three-tier supervision (sentinel -> orchestrator -> agents) enables overnight unattended runs. The "auto-kill incident" (watchdog killed an agent mid-write, corrupting a 500-line file) taught us: unreliable heuristics destroy work — use deterministic gates instead.

### Phase 7: Verification + Spec Coverage (Mar 8--15)

Quality gates evolved beyond "do tests pass?" to "did the agent build what was specified?" Multi-file spec digestion parsed complex product specs into individual requirements. Requirement-level coverage tracking mapped each requirement to the code that implemented it. HTML reporting gave a visual overview of what was covered and what was missing.

Intensive E2E benchmarks (CraftBrew runs #3--5) surfaced dozens of bugs that unit tests never caught: token tracking overflow at 10M+ tokens, watchdog false positives during `pnpm install` (which can take 60+ seconds), zombie process cleanup failing when PIDs were recycled, race conditions between the 15-second poll cycle and agent completion events.

**Key insight:** Complex specs (CraftBrew: 15+ changes, Figma designs, i18n) require spec-level verification, not just "do tests pass." An agent can make all tests green while implementing only half the requirements.

### Phase 8: Production-Grade (Mar 15--21)

The merge pipeline gained integrity protection: conservation checks (did the merge lose any code?), entity counting (are all database models still present?), and LLM-assisted conflict resolution for cross-cutting files like Prisma schemas and i18n message bundles.

Cumulative review feedback meant that review comments from early changes informed later reviews — if the reviewer flagged a pattern in change #2, change #5 got warned about the same pattern. The integrate-then-verify pipeline ensured no change merged without passing gates against the latest main.

**CraftBrew run #7: 14/14 merged — first 100% completion on a complex multi-file spec.** This was the validation milestone. 15 changes, 150+ source files, 28 database tables, Figma design integration, i18n support — all built autonomously.

Renamed the project from **wt-tools** to **SET (Ship Exactly This)**.

**Key insight:** The 100% CraftBrew completion proved the system works end-to-end. The rename reflected the evolved identity — this was no longer a worktree management tool.

### Phase 9: Modular Architecture + Web Dashboard (Mar 21--25)

The biggest refactor: monorepo module migration consolidated 3 separate repos (`set-core`, `set-project-base`, `set-project-web`) into 1 monorepo with a plugin system. The profile-driven gate registry let each project type define its own quality gates. The issue management engine with detection bridge automatically created issues from gate failures.

The web dashboard replaced the PyQt GUI with a browser-based operations center: unified navigation across projects, real-time sentinel status, session logs with token tracking, Discord integration for notifications, and a process manager with tree view showing all running agents.

![Web dashboard changes tab](../images/auto/web/tab-changes.png)

**Key insight:** The architecture crystallized into three layers: core (abstract engine), modules (project-type plugins), and external plugins (separate repos). The web dashboard became an operations center, not just a status display.

### Phase 10: Auto-Fix + Release (Mar 25--28)

The last mile: when quality gates fail, what happens? Previously, a human had to diagnose and fix. The auto-fix pipeline changed this — investigation agents analyze gate failures, diagnose root causes, and apply fixes autonomously. A failing Jest test triggers an investigation agent that reads the test output, identifies the bug, fixes the code, and re-runs the gate.

The three-layer template system reduced file structure divergence from 63% to 0% across consumer projects. Every project initialized with `set-project init` gets identical directory structure, rules, and configuration. The unified web service consolidated 3 separate servers (API, dashboard, manager) onto a single port. The automated screenshot pipeline captures app screenshots after every successful run for documentation.

**19 active changes in flight, 329 archived.** The full [18-chapter technical reference](../howitworks/en/01-overview.md) was written. The Battle View game was born as a fun way to visualize orchestration runs.

**Key insight:** The auto-fix pipeline closed the last gap — when gates fail, the system diagnoses and fixes without human intervention. The framework became truly self-healing.

## Architecture Evolution

```
Jan:  CLI scripts (bash)           -> "worktree management tools"
Feb:  GUI + Memory + Ralph Loop    -> "agent development environment"
Mar:  Orchestration + Sentinel     -> "autonomous development framework"
      + Gates + Web + Auto-Fix     -> "self-healing orchestration system"
```

Each phase was driven by real failures in real E2E runs — not theoretical design. The CraftBrew and MiniShop benchmarks were the forcing functions that exposed every weakness.

## Key Insights

1. **Structure beats prompts.** OpenSpec artifacts constrain agents more reliably than instructions. A proposal with explicit IN SCOPE / OUT OF SCOPE boundaries prevents 90% of agent drift.
2. **Deterministic beats smart.** Exit-code gates catch what LLM review misses. `jest --ci` returning exit code 1 is more reliable than asking an LLM "did this code look correct?"
3. **Merges are the danger zone.** Phase ordering and dependency DAGs prevent cascading conflicts. Without them, 5 parallel changes touching the same Prisma schema cause exponential rework.
4. **Memory needs infrastructure.** Agents won't save voluntarily — zero saves across 15+ sessions. Hooks at every lifecycle point make memory automatic.
5. **E2E is the only real test.** Unit tests pass, orchestration runs fail. The interactions between digest, planner, dispatcher, verifier, and merger create emergent behaviors that only surface in full runs.
6. **Templates beat conventions.** Pre-deployed files eliminate 63% of output divergence. Telling agents "create a Next.js project" produces wildly different results; giving them a template produces consistent ones.
7. **The sentinel pays for itself.** 5--10 LLM calls per run saves hours of wasted compute. A single undetected crash at 2 AM wastes the entire overnight run.

---

*See also: [Benchmarks](benchmarks.md) · [Lessons Learned](lessons-learned.md) · [How It Works](how-it-works.md)*

<!-- specs: orchestration-engine, sentinel-dashboard, gate-profiles, hook-driven-memory, modular-source-structure -->
