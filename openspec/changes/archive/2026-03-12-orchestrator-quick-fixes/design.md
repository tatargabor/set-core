## Context

Three bugs discovered during multi-phase E2E orchestration runs cause hangs, incorrect metrics, and blocked replan cycles. All three are isolated to specific functions with minimal blast radius.

**Current state:**
- `cascade_failed_deps()` exists but is called AFTER `dispatch_ready_changes()` in the monitor loop, creating a race window where deadlocked changes accumulate
- `any_loop_active()` only checks "running" status, missing "verifying" changes — timer stops during verify phases
- Replan auto-re-digest has no skip logic when spec hash is unchanged, and no fallback when re-generation fails

## Goals / Non-Goals

**Goals:**
- Eliminate dependency deadlock when a change fails (cascade before dispatch)
- Ensure active_seconds increments during verify phases for correct time_limit enforcement
- Prevent digest JSON parse failures from blocking replan when specs haven't changed

**Non-Goals:**
- Worktree-gone crash recovery (#14) — requires separate change with PID liveness checks and edge case handling
- Tech-specific verify hints (#15) — existing memory system sufficient
- Digest JSON parser hardening — separate concern; hash-based skip eliminates the trigger

## Decisions

### D1: Reorder cascade before dispatch (monitor.sh)

Move `cascade_failed_deps()` call from after `dispatch_ready_changes()` to before it. This ensures failed dependency chains are resolved before new dispatches are attempted.

**Why not modify `deps_satisfied()` directly?** Adding side effects (status updates) to a predicate function violates single-responsibility. The existing cascade function is purpose-built for this — just needs correct call ordering.

**Alternatives considered:**
- Modify `active_count` calculation to exclude deadlocked pending changes — complex jq, fragile
- Add cascade as a side effect in `deps_satisfied()` — breaks function contract (predicate with mutations)

### D2: Add "verifying" to any_loop_active() check (utils.sh)

Add `"verifying"` status alongside `"running"` in `any_loop_active()`. During verify, the orchestrator IS actively running tests/builds — this is real work that should count toward active_seconds and time_limit.

**Caveat:** loop-state.json mtime will be stale during verify (Ralph isn't updating it), but the function will still return true because the status check passes before the mtime check. This is correct behavior — verify IS active work even though Ralph isn't the one doing it.

### D3: Hash-based skip for unchanged digest during replan (planner.sh)

In the auto-re-digest trigger (planner.sh), add a redundant hash check: if spec source_hash matches the stored digest hash, skip re-digest entirely. This prevents the JSON parse failure scenario because no Claude API call is made.

**Why not also add fallback to cached digest?** It hides errors and could cause wrong plans if specs actually changed. The hash-based skip is sufficient — if hash matches, the cached digest is definitionally correct. If hash doesn't match, re-digest is genuinely needed and parse failure should be reported.

## Risks / Trade-offs

- [Risk: cascade runs before dispatch could mark a change failed that's "about to be dispatched"] → Not possible: cascade only processes pending changes whose dependencies are already failed. If a change CAN be dispatched, its deps are merged/skipped, not failed.
- [Risk: any_loop_active returns true during verify but loop-state.json is stale] → Acceptable: the function returns true because status="verifying" exists, which is correct. The mtime check is a secondary heuristic.
- [Risk: hash-based skip reuses stale digest if someone edits specs mid-orchestration] → Acceptable: spec edits during orchestration are already unsupported. If hash genuinely differs, normal re-digest path runs.
