[< Back to Index](../INDEX.md)

# Lessons Learned — Production Insights

Key insights from 30+ autonomous orchestration runs across real projects.

## 1. Agents Need Structure, Not Just Prompts

Without OpenSpec artifacts, agents drift — they skip requirements, make inconsistent architecture decisions, and produce code that doesn't match the spec. The proposal → specs → design → tasks pipeline keeps them focused.

**What we did:** Built the OpenSpec workflow with dependency-tracked artifacts. Each agent gets a proposal with explicit scope boundaries (IN SCOPE / OUT OF SCOPE). Task lists link back to spec requirements with `[REQ: ...]` tags.

## 2. Quality Gates Must Be Deterministic

Early versions used LLM-judged code review as a merge gate. The result: inconsistent pass/fail decisions, agents gaming the reviewer, and false positives that let bugs through.

**What we did:** Made test, build, and E2E gates deterministic (exit code 0 or not). Only code review remains LLM-based, with explicit PASS/FAIL parsing. Lint gate uses pattern matching, not LLM judgment.

## 3. Merge Conflicts Are the #1 Cascading Failure

When 5 changes merge simultaneously, each failed ff-only merge triggers a full re-gate cycle (build + test + review). Parallel changes touching the same files (Prisma schema, i18n messages, middleware) cause the most damage.

**What we did:** Phase-ordered execution (changes in phase 2 only start after phase 1 merges), dependency DAG to prevent conflicting parallel work, and automatic main integration before merge attempts.

## 4. Memory Without Save Hooks Is Useless

Across 15+ agent sessions in benchmarks, agents made zero voluntary memory saves. They're too focused on the immediate task to remember to save context for future sessions.

**What we did:** Built 5-layer hook infrastructure that automatically extracts and saves insights at session boundaries, after tool calls, and on errors. Memory is now an infrastructure concern, not an agent behavior.

## 5. E2E Testing the Orchestrator Reveals Bugs No Unit Test Catches

Unit tests pass but real orchestration runs fail — because the interactions between digest, planner, dispatcher, verifier, and merger create emergent behaviors. Stale locks, zombie processes, race conditions between poll cycles.

**What we did:** Built a full E2E test infrastructure (`tests/e2e/run.sh`) that scaffolds a project, runs the complete orchestration, and validates results. Each E2E run produces a benchmark report with per-change metrics.

## 6. Stall Detection Needs Grace Periods

Agents go silent during large file writes, Prisma migrations, or `pnpm install`. Without grace periods, the watchdog kills them prematurely.

**What we did:** Added expected-pattern awareness — the watchdog recognizes known long-running operations (post-merge codegen, package install, MCP fetch) and extends the timeout.

## 7. The Sentinel Pays for Itself

A single undetected crash at 2 AM wastes the entire run. The sentinel costs ~5-10 LLM calls per run (for decision-making) but saves hours of wasted compute by detecting and recovering from crashes within 30 seconds.

---

*See also: [Benchmarks](benchmarks.md) · [Journey](journey.md) · [How It Works](how-it-works.md)*

<!-- specs: orchestration-watchdog, sentinel-polling, gate-profiles, hook-driven-memory -->
