# Lessons Learned and Challenges

## Solved Problems

The following were discovered during live orchestration runs — typically lessons from the first few production runs (sales-raketa, MiniShop, CraftBrew).

### Token Budget Calibration

**Problem**: The original budget tiers (S=500K, M=2M) were too low. Artifact generation overhead (proposal → design → specs → tasks) already requires 500K-800K tokens before implementation even starts.

**Solution**: Calibration from live data: S=2M, M=5M, L=10M. Production runs confirmed: a typical S change uses 1.3-1.5M tokens (including artifact overhead).

### Watchdog Spam

**Problem**: The watchdog emitted `WATCHDOG_WARN` events every 15 seconds — for a slow change, 60+ entries in the event log, degrading sentinel liveness detection and bloating log size.

**Solution**: Throttle event emission: only write to the log every 20th occurrence.

### Sentinel Filename Mismatch

**Problem**: The sentinel watched `orchestration-events.jsonl` (hardcoded), but the orchestrator wrote to `orchestration-state-events.jsonl` (dynamic name). Result: the sentinel killed healthy orchestrators after 180 seconds.

**Solution**: The sentinel now derives the events filename from the state filename instead of hardcoding.

### Misleading Token Tracking

**Problem**: Cache tokens counted toward the budget but didn't appear in tracking — 18x discrepancy between displayed and actual consumption.

**Solution**: Include cache tokens in tracking.

### Large Change Reliability

**Problem**: 14+ requirements in a single change → 40+ minutes, 3 verify retries → failed. The cause: the context window isn't large enough, the agent loses track.

**Solution**: The planner applies a max 6 REQ/change rule. Changes with 4-6 requirements run reliably (12-19 minutes, 0 retries).

### Jest + Playwright Collision

**Problem**: Jest unit tests crashed on Playwright `.spec.ts` files ("TypeError: Class extends value undefined") because jsdom can't handle browser imports.

**Solution**: `testPathIgnorePatterns` in jest config + per-worktree port isolation for Playwright tests.

## Known Limitations

### Mock-Based Tests Hide Runtime Errors

**Problem**: Jest tests mock Next.js APIs (`cookies()`, `headers()`), so they don't catch runtime errors. In the MiniShop run, 81 Jest tests were green while the application had 3 critical runtime bugs (auth bypass, cookie crash, dead link).

**Lesson**: Smoke testing (`pnpm build && pnpm test`) and E2E testing (`Playwright`) are needed together. Build catches type errors, E2E catches functional regressions.

### Merge Conflicts on Shared Resources

**Problem**: Parallel changes modify the same file (e.g., `functional-conventions.md`, layout components). LLM merge can't resolve 900+ line conflicts.

**Future**: The planner should recognize cross-cutting files and serialize changes instead of parallelizing them.

### Context Loss After Merge

**Problem**: After a schema change merge: code compiled correctly in the worktree, but on main (where other changes also modified the schema) TypeScript errors appeared.

**Lesson**: Post-merge build verification (`base build health check`) is essential.

### Memory Doesn't Guarantee Quality

**Problem**: Benchmark runs showed that agents with memory explored 50% less but produced lower quality code — memory provides "shortcuts" that bypass the thorough code reading needed for complex changes.

**Lesson**: "Recall-then-verify" pattern: after memory recall, always verify the current state of the codebase.

## What's Still Ahead

### Cascade Failure Logic

When a change fails, dependent changes currently remain pending forever. Needed: automatic cascade failure propagation that moves dependent changes to `skipped` status.

### Trend-Based Token Budget

Static budget limits (S=2M, M=5M) don't scale to every project. Needed: project-level learning from actual token consumption, automatic limit adjustment.

### Agent Scoring for Dispatch

Currently dispatch is round-robin. Needed: scoring agents by error rate, token efficiency, and iteration/progress ratio — better agents get more tasks.

### Circuit Breaker for API Calls

On consecutive API errors, the system doesn't stop but keeps trying. Needed: circuit breaker pattern that stops after N consecutive failures.

\begin{keypoint}
The real value of orchestration shows from the second run onward. The first run always reveals problems — wrong budget, missing test configuration, unexpected merge conflicts. The point: every error occurs only once, because the system learns from it (watchdog tuning, budget calibration, planner rules).
\end{keypoint}
