[< Back to Index](../INDEX.md)

# Development Journey

**1,294 commits · 329 archived changes · 363 specs · 79 days**

set-core was built with set-core. Every feature was planned through OpenSpec, implemented by agents, and validated through quality gates.

## By The Numbers

| Metric | Value |
|--------|-------|
| Development | 950+ hours across 79 days (Jan 9 – Mar 28, 2026) |
| Commits | 1,294 (~16/day) |
| Capability specifications | 363 |
| Archived OpenSpec changes | 329 |
| Total codebase | 134K LOC |
| — Python (engine, GUI, modules) | 59,000 |
| — Shell scripts (CLI tools) | 15,000 |
| — TypeScript (dashboard) | 14,000 |
| — OpenSpec specs | 23,000 |
| — Docs + templates + rules | 22,000 |
| Autonomous agent runtime | 720+ hours (~60 days × 12h/day continuous) |
| Best benchmark | CraftBrew run #7: 14/14 merged (100%) |

## Development Timeline

### Phase 1: Worktree Tools (Jan 9–24)

The project began as **wt-tools** — bash CLI scripts for managing parallel Claude Code agents via git worktrees. `wt-new`, `wt-work`, `wt-list`, `wt-close`, `wt-merge`. JIRA integration, file activity tracking, multi-machine worklog support.

**Key insight:** Git worktrees are the natural unit of parallel AI agent work — real branches, real isolation, real merges.

### Phase 2: GUI Control Center + Team Sync (Jan 24–29)

30+ changes in one week: PyQt-based Control Center (worktree table, status indicators, running animations), team sync (multi-agent messaging), multi-editor support (VS Code, Zed, Cursor), context menu system.

**Key insight:** Developers need visual feedback when managing multiple parallel agents. CLI-only doesn't scale.

### Phase 3: Memory Integration (Feb 11–17)

Integrated shodh-memory across the entire workflow. GUI memory browser, OpenSpec lifecycle hooks, proactive mid-flow recall. Fixed RocksDB lock contention causing silent data loss.

Built the CraftBazaar benchmark — synthetic test protocol measuring memory effectiveness. Six benchmark runs achieved **+34% weighted improvement** with memory enabled.

**Key insight:** Agents don't save memories voluntarily (zero saves observed across 15+ sessions). Infrastructure must handle it via hooks.

### Phase 4: Ralph Loop + Autonomous Agents (Feb 15–19)

Built the Ralph Loop — autonomous agent iterations with stall detection, done criteria, and per-change iteration tracking. Built the 5-layer hook architecture (frustration detection, commit-save, transcript extraction, branch-aware tagging).

**Key insight:** Single-shot agent prompts fail on complex tasks. Iterative loops with trend detection and auto-pause are the reliable pattern.

### Phase 5: Orchestration Engine (Feb 25–27)

The architectural leap: **set-orchestrate** — accepts a spec, decomposes via LLM into a dependency DAG, dispatches to parallel worktrees, monitors, and auto-replans. Token budgets, time limits, audit system.

**Key insight:** This was the transition from "tool that helps developers" to "autonomous framework that builds projects from specs."

### Phase 6: Sentinel + Merge Pipeline (Mar 2–8)

Built the sentinel supervisor — non-blocking polls, crash diagnosis, auto-restart. Hardened merge pipeline: sequential queue, post-merge smoke testing, empty-merge detection.

Decomposed the monolithic orchestrator into 7 library modules. Built the events system, watchdog escalation chains, quality gate hooks. Created the MiniShop E2E test scaffold.

**Key insight:** Three-tier supervision (sentinel → orchestrator → agents) enables overnight unattended runs. The auto-kill incident taught us: unreliable heuristics destroy work — use deterministic gates instead.

### Phase 7: Verification + Spec Coverage (Mar 8–15)

Multi-file spec digestion, requirement-level coverage tracking, HTML reporting. Intensive E2E benchmarks (runs #3–5) surfaced dozens of bugs: token tracking, watchdog false positives, zombie cleanup.

**Key insight:** Complex specs (CraftBrew: 15+ changes, Figma designs, i18n) require spec-level verification, not just "do tests pass."

### Phase 8: Production-Grade (Mar 15–21)

Merge integrity protection (conservation check, entity counting). Context-aware merge with LLM conflict resolution. Cumulative review feedback. Integrate-then-verify pipeline.

**CraftBrew run #7: 14/14 merged — first 100% completion on a complex multi-file spec.**

Renamed the project from **wt-tools to SET (Ship Exactly This)**.

**Key insight:** The 100% CraftBrew completion proved the system works end-to-end. The rename reflected the evolved identity.

### Phase 9: Modular Architecture + Web Dashboard (Mar 21–25)

Monorepo module migration (3 repos → 1). Profile-driven gate registry. Issue management engine with detection bridge. Web dashboard with unified navigation, sentinel launch, Discord integration. Process manager with tree view.

**Key insight:** The architecture crystallized into three layers (core/modules/plugins). The web dashboard became an operations center, not just a status display.

### Phase 10: Auto-Fix + Release (Mar 25–28)

Auto-fix pipeline — investigation agents diagnose and fix problems autonomously. Three-layer template system for divergence reduction (63% → 0% file structure divergence). Unified web service on a single port. Automated screenshot pipeline. Full documentation rewrite.

**19 active changes in flight, 329 archived.** The Battle View game was born.

**Key insight:** The auto-fix pipeline closed the last gap — when gates fail, the system diagnoses and fixes without human intervention.

## Architecture Evolution

```
Jan:  CLI scripts (bash)           → "worktree management tools"
Feb:  GUI + Memory + Ralph Loop    → "agent development environment"
Mar:  Orchestration + Sentinel     → "autonomous development framework"
      + Gates + Web + Auto-Fix     → "self-healing orchestration system"
```

Each phase was driven by real failures in real E2E runs — not theoretical design.

## Key Insights

1. **Structure beats prompts.** OpenSpec artifacts constrain agents more reliably than instructions.
2. **Deterministic beats smart.** Exit-code gates catch what LLM review misses.
3. **Merges are the danger zone.** Phase ordering and dependency DAGs prevent cascading conflicts.
4. **Memory needs infrastructure.** Agents won't save voluntarily. Hooks at every lifecycle point.
5. **E2E is the only real test.** Unit tests pass, orchestration runs fail — emergent behaviors.
6. **Templates beat conventions.** Pre-deployed files eliminate 63% of output divergence.
7. **The sentinel pays for itself.** 5–10 LLM calls per run saves hours of wasted compute.

---

*See also: [Benchmarks](benchmarks.md) · [Lessons Learned](lessons-learned.md) · [How It Works](how-it-works.md)*

<!-- specs: orchestration-engine, sentinel-dashboard, gate-profiles, hook-driven-memory, modular-source-structure -->
