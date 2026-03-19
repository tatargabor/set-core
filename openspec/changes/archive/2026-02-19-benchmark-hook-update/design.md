## Context

The benchmark has two init scripts and two CLAUDE.md templates. Run A (baseline) has no memory. Run B (with-memory) uses the old "Proactive Memory" pattern with manual `set-memory recall/remember` commands. The hook system (`wt-hook-memory`) now handles all this automatically via `wt-deploy-hooks`.

## Goals / Non-Goals

**Goals:**
- Make benchmark Run B use the current hook-driven memory system
- Remove deprecated `set-memory-hooks` dependency
- Keep the Benchmark Task workflow section intact (it's benchmark-specific, not memory-specific)

**Non-Goals:**
- Changing Run A (baseline) — it correctly has no memory
- Changing the scoring rubric or test scripts
- Adding new benchmark changes

## Decisions

### Decision 1: Replace Proactive Memory with Persistent Memory

**Choice:** Replace the entire "Proactive Memory" section (manual recall/remember/reflection) with the "Persistent Memory" section from set-core CLAUDE.md. Keep the section minimal — hooks handle everything, agent only needs `remember` for emphasis.

### Decision 2: Keep "Recall-then-verify" as a note

**Choice:** Add a one-line note about verifying recalled info against codebase. The old CLAUDE.md had a full "Recall-then-verify" section — this is still good advice but can be shortened since hooks handle the recall automatically.

## Risks / Trade-offs

**[Risk] Benchmark comparability** → v7 results won't be directly comparable to v6 since the memory interaction pattern changed. This is expected — we're testing the current system, not the old one.
