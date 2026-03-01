## Context

The Ralph loop (`wt-loop`) already has stall detection: if N consecutive iterations produce no commits, it stops with "stalled" status. However, it has a blind spot in OpenSpec mode (`done_criteria: openspec`): when `detect_next_change_action()` returns `ff:<change>` but the `opsx:ff` skill fails to create `tasks.md`, the loop retries `ff:` indefinitely. Each iteration *does* produce artifact files (proposal.md, design.md), so the stall counter resets, but the loop never progresses.

The worktree bootstrap (`wt-new`) runs `pnpm install` but doesn't copy `.env` files, causing build/test failures in worktrees.

Token tracking exists per-iteration in `loop-state.json` (field: `total_tokens`), but there's no budget enforcement — a stuck S-sized change can burn 150K+ tokens with no circuit breaker.

## Goals / Non-Goals

**Goals:**
- Prevent infinite `ff:` retry loops by tracking ff attempts per change and escalating after max retries
- Add fallback done criteria for targeted openspec changes when tasks.md is absent but work is complete
- Copy `.env` and `.env.local` from main repo to worktrees during bootstrap
- Enforce per-change token budgets with checkpoint escalation
- Reduce memory pollution from no-op loop iterations

**Non-Goals:**
- Restructuring the overall Ralph loop architecture
- Changing how `opsx:ff` itself creates artifacts (that's a separate concern)
- Adding new done criteria types beyond the existing set
- Modifying the orchestrator's stall detection (already uses 300s threshold + PID check)

## Decisions

### D1: FF retry tracking in `detect_next_change_action`

Add `ff_attempts` tracking in the Ralph loop's main iteration loop, NOT inside `detect_next_change_action()` itself (which is a pure function).

**Approach:** In `cmd_run()`, after executing an `ff:` action, check if `tasks.md` was created. If not, increment a counter. After 2 failed attempts, switch the action to `"stale"` which triggers a checkpoint/escalation instead of retrying.

**Why not modify `detect_next_change_action()`:** It's a stateless function that inspects filesystem state. Adding retry tracking there would make it impure and harder to test. The retry logic belongs in the caller.

### D2: Fallback done for targeted openspec changes

When `done_criteria: openspec` with a `--change` target, and `detect_next_change_action()` returns `ff:<change>` but the ff_attempts limit is exceeded, treat the change as having an artifact problem (not a code problem). Mark as `stalled` with a descriptive message rather than silently spinning.

**Why not treat as "done":** A missing tasks.md means the planning phase failed. Treating it as "done" could skip implementation entirely. Better to stall with a clear message so the orchestrator can handle it (re-plan, manual intervention, etc.).

### D3: Token budget enforcement via loop-state thresholds

Add `--token-budget` flag to `wt-loop start` (default: 0 = unlimited). The orchestrator sets this based on change size. During the iteration loop, after updating `total_tokens`, compare against budget. If exceeded, stop with status `"budget_exceeded"` — a new status that the orchestrator treats like a checkpoint.

**Budget defaults (set by orchestrator, not by wt-loop):**
| Size | Budget |
|------|--------|
| S | 100K |
| M | 300K |
| L | 500K |
| XL | 1M |

**Why a new status instead of reusing "stalled":** Budget exceeded is informational, not an error. The orchestrator may want to extend the budget and resume, which is different from stall recovery.

### D4: .env bootstrap in wt-new

Add `.env` and `.env.local` copying after `bootstrap_dependencies()` in `wt-new`. Copy from the main repo (resolved via `git worktree list`'s first entry). Skip if source doesn't exist.

**Why after dependencies:** The `.env` may be needed by post-install scripts. Order: create worktree → copy .env → install dependencies. Actually, reorder: copy .env BEFORE dependency install since some install scripts read env vars.

### D5: Memory save guard for no-op iterations

The reflection dedup already exists (lines 920-953 of wt-loop). Extend it: if `new_commits == "[]"` AND `has_artifact_progress == false` AND `reflection_content` is trivial, skip the memory save entirely and add a flag to the iteration record: `"no_op": true`.

The session-end hook already runs externally — the Ralph loop cannot control it directly. But the loop CAN write a `.claude/loop-iteration-noop` marker file that the session-end hook checks. If present, the hook skips memory extraction.

## Risks / Trade-offs

- **[Risk] FF attempt limit too low** → A legitimate slow artifact creation (large project context) could be wrongly limited. Mitigation: default 2 retries is conservative; the orchestrator can re-dispatch.
- **[Risk] Budget enforcement kills productive work** → A change near budget limit doing useful work gets cut off mid-task. Mitigation: check budget only between iterations, not mid-iteration. The agent finishes its current iteration before stopping.
- **[Risk] .env contains secrets, copied to worktree** → Worktrees are on the same machine, same user, same permissions. No additional exposure. The .env is gitignored in the worktree too.
- **[Risk] No-op marker file left behind** → If loop crashes before cleanup, the marker persists. Mitigation: the marker includes a timestamp; the session-end hook ignores stale markers (>1 hour old).
