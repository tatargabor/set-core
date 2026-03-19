## Context

The orchestrator (`set-orchestrate`) can plan, dispatch, and merge changes at scale, but the v3 sales-raketa run revealed that speed came at the cost of quality: no tests, no build checks, duplicate changes, and broken worktree environments. The verify gate had test execution and code review but lacked build verification and test existence awareness. Worktree creation had no dependency or environment bootstrapping.

## Goals / Non-Goals

**Goals:**
- Eliminate manual worktree setup (`.env` copy, `pnpm install`)
- Surface missing tests as a warning before merge
- Block merging code that doesn't build
- Detect duplicate/overlapping changes at plan time before wasting compute

**Non-Goals:**
- Enforcing test coverage thresholds (future work)
- Seed data enforcement (future work)
- LLM-based semantic deduplication (keyword jaccard is sufficient for now)
- Fixing shadow DB migration bugs (project-specific, not orchestrator-level)

## Decisions

1. **Worktree bootstrap in wt-new, not set-orchestrate** — Bootstrap logic lives in `wt-new` so both manual and orchestrated worktrees benefit. The orchestrator calls `wt-new` so it inherits the behavior automatically.

2. **Test file check is WARNING, not blocking** — Some changes genuinely don't need tests (doc updates, config changes). Hard-blocking would create false failures. The warning is logged, stored in state (`has_tests` field), and sent as a notification.

3. **Build step is blocking with retry** — Unlike test file existence, a failing build is always wrong. Uses the same retry mechanism as test failures (resume Ralph with build error context).

4. **Scope overlap uses keyword jaccard, not LLM** — Jaccard similarity on lowercase words (3+ chars) is fast, deterministic, and free. Threshold of 40% catches obvious overlaps without false positives on related-but-distinct changes. Checks both plan-internal pairs and plan-vs-active-worktrees.

5. **Package manager auto-detection via lockfile** — `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `bun.lockb`/`bun.lock` → bun, `package-lock.json` → npm. Falls back gracefully if lockfile or PM binary is missing.

## Risks / Trade-offs

- **Bootstrap install time** — `pnpm install` adds 10-30s per worktree creation. Acceptable given it saves agent time later and prevents "vitest not found" failures.
- **Jaccard false negatives** — Two changes with different wording but same intent won't be caught. This is acceptable for v1; LLM-based detection is a future enhancement.
- **Build step adds verify gate latency** — Build can take 30-120s. This is offset by catching broken builds before merge instead of after.
- **Frozen lockfile fallback** — `--frozen-lockfile` is tried first, falling back to regular install. This means worktree lockfiles might diverge from main if schema changes happened. Non-fatal since the agent will fix any issues.
