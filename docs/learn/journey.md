[< Back to Index](../INDEX.md)

# Development Journey

**1,870 commits · 424 archived changes · 429 specs · 109 days**

set-core was built with set-core. Every feature was planned through OpenSpec, implemented by agents, and validated through quality gates. The framework bootstrapped itself — by Phase 5, the orchestration engine was building its own next features.

## By The Numbers

| Metric | Value |
|--------|-------|
| Development | Jan 9 — Apr 27, 2026 (109 days) |
| Commits | 1,870 (~17/day) |
| Capability specifications | 429 |
| Archived OpenSpec changes | 424 |
| Active changes in flight | 5 |
| Python codebase (engine, GUI, modules) | 89,000 LOC |
| TypeScript codebase (dashboard) | 20,000 LOC |
| Built-in modules | `web` (Next.js + Prisma + Playwright), `example` (reference plugin) |
| Latest release | v1.7.1 (Apr 16) — v1.8 in prep |
| Best multi-change benchmark | CraftBrew run #7: 14/14 merged, 100% completion |
| Best lean benchmark | MiniShop: 6/6 merged, 0 interventions, 1h 45m |

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

### Phase 11: v0 Pipeline + Robustness (Mar 28 — Apr 27)

The post-v1.7 era. Two parallel arcs reshaped the framework:

**v0.app design pipeline.** The Figma Make → `set-design-sync` flow shipped in Phase 8 had three real failure modes: opaque binary `.make` files (3.9 MB ZIPs that couldn't be diffed), Figma's color naming colliding with shadcn primitive pairs (causing invisible text), and missing interactive states (hover, selected, disabled). The fix wasn't to patch Figma — it was to swap the entire upstream. **v0.app** generates shadcn/ui + Tailwind + Next.js code natively; the export is the design source. `set-design-import` clones a v0 repo, generates a manifest with shell components, routes, and component bindings, and the dispatcher writes a per-change `design.md` slice into each agent's input. The `design-fidelity-gate` runs a JSX structural parity check on every UI change — if the agent diverges from the v0 export's component structure, merge is blocked with a diff. Layer 1 lost all `build_per_change_design()` and `bridge.sh` references; Layer 2 (`modules/web`) owns the v0-specific logic.

**Engine and issue lifecycle robustness.** Production E2E runs surfaced edge cases that the original design papered over: stuck `dispatched` states, poisoned stalls (agent looping on the same hash), merge-stalled FF retries that never converged, integration-conflict re-dispatch races, ghost duplicate `fix-iss` children, orphaned `_retry_parent_after_resolved` cleanup. Each got its own surgical fix and circuit-breaker. Retry budgets were unified into a single `DIRECTIVE_DEFAULTS` source of truth, with a `tests/unit/test_config_engine_parity.py` parity test that prevents silent divergence between `config.py` and the runtime `Directives` dataclass. The `IssueRegistry` learned to register circuit-breaker escalations (`merge_stalled`, `token_runaway`) as first-class issues so the existing fix-iss pipeline could investigate and resolve them. When a parent change auto-recovers from a `failed:*` terminal state, on-disk worktree and `change/<name>` branch are cleaned up before the in-memory state reset, so re-dispatch starts on a fresh tree.

**Forensics and cost.** A 10× cost inflation bug (input_tokens included `cache_read_input_tokens`, double-counting the cache hit) was found and fixed mid-month — historical USD figures need recompute. `set-run-logs` and the `/set:forensics` skill make post-run debugging a single command instead of a JSONL grep tour. The activity dashboard gained per-iteration session attribution (`AGENT_SESSION_DECISION` events) and per-gate span reconstruction from `VERIFY_GATE` events — every minute of every run is now placed on a real-time axis.

**Spec hygiene.** The `dynamic-category-injection` change wired up multi-layer category resolution (core → module → scaffold → project) so each change's input.md gets the right set of rules without manual config. `design-binding-completeness` added the `set-design-hygiene` CLI with 9 antipattern rules — mock arrays inline, hardcoded UI strings, broken route references, locale-prefix inconsistencies — that operators run before adopting a v0 export.

**Cleanup pass (Apr 27).** A bulk-archive operation closed 35 changes — 7 completed (design-binding-completeness, dynamic-category-injection, fix-iss-lifecycle-hardening, fix-merge-worktree-collision, improve-investigator-robustness, tsconfig-and-gitignore-template-hardening, v0-design-pipeline) and 28 stale or manual-only-remaining (verify-gate-resilience-fixes, review-gate-integration, etc.). Active openspec list dropped from 40 to 6.

**Key insight:** The framework's reliability gradient flipped between Phase 9 and Phase 11. In Phase 9, every E2E run surfaced new bugs that needed fixing in core. In Phase 11, runs surfaced edge cases that already had circuit-breakers and auto-recovery — the system absorbed the failures without operator intervention. The shift wasn't a single feature; it was the cumulative effect of 173 commits worth of surgical resilience work, each fix coming from a real production incident.

## Architecture Evolution

```
Jan:  CLI scripts (bash)              -> "worktree management tools"
Feb:  GUI + Memory + Ralph Loop       -> "agent development environment"
Mar:  Orchestration + Sentinel        -> "autonomous development framework"
      + Gates + Web + Auto-Fix        -> "self-healing orchestration system"
Apr:  v0 design + Issue lifecycle     -> "production-grade orchestration platform"
      + Forensics + Cost + Hygiene
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
8. **Cost is a first-class metric.** USD per change, USD per gate, USD per agent session — without it, "is this orchestration affordable?" is unanswerable. The 10× inflation bug from `cache_read_input_tokens` double-counting hid for weeks because nothing was watching the line.
9. **Circuit-breakers beat retries.** A bounded retry budget with an explicit escalation path (failed:* → fix-iss → investigator → resolver → parent retry) is more reliable than uncapped retry loops. The hard part is choosing where the escalation goes.
10. **Design as code, not as image.** v0.app exports are diffable, reviewable, version-controlled — the agent reads the same source the human did. Binary design files (Figma `.make`) hide their semantics; reviewers can't tell why a token changed.

---

*See also: [Benchmarks](benchmarks.md) · [Lessons Learned](lessons-learned.md) · [How It Works](how-it-works.md)*

<!-- specs: orchestration-engine, sentinel-dashboard, gate-profiles, hook-driven-memory, modular-source-structure -->
