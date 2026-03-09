## Why

The sentinel currently tries to diagnose and restart orchestrator crashes, but it also intervenes in situations the orchestrator can handle itself on the next run (e.g., merge-blocked changes that resolve with the new jq deep-merge, transient test failures). This wastes sentinel context tokens on diagnosis that adds no value, and in worst cases the sentinel modifies state or files it shouldn't touch — violating its own role boundary. The sentinel should clearly distinguish between "orchestrator will handle this" vs "this needs human intervention" and only act on the latter.

## What Changes

### Sentinel deference (prompt-only)
- Add a "Deference Principle" section to the sentinel skill that explicitly categorizes situations into "defer to orchestrator" vs "escalate to user"
- Remove/simplify crash recovery logic for cases the orchestrator already handles (merge-blocked retry, verify retry, replan cycles)
- Add guidance for merge-blocked changes: sentinel should NOT manually resolve conflicts or set status — the orchestrator's retry_merge_queue with jq deep-merge handles this
- Add guidance for test/verify failures: sentinel should NOT restart or intervene — orchestrator has max_verify_retries and fix cycles built in
- Clarify that sentinel restarts are ONLY for process-level crashes (SIGKILL, OOM, broken pipe), not for orchestration-level issues (a change failing, a merge conflicting)
- Update the EVENT:process_exit handler to check if the orchestrator exited with a recoverable orchestration-level reason vs an actual process crash

### wt-loop API error handling (code change)
- Detect Claude API errors (429, 503, connection reset) in wt-loop and enter backoff/wait state instead of burning iteration budget
- Add `waiting:api` loop status distinct from `stalled`
- Implement exponential backoff (30s→60s→120s→240s) matching sentinel's pattern
- Parse claude CLI exit codes and stderr for API-specific errors
- Sentinel should recognize `waiting:api` as a transient state (not stalled)

## Capabilities

### New Capabilities
- `sentinel-deference`: Rules and classification for when sentinel should defer to orchestrator vs escalate to user
- `loop-api-error-handling`: Detect API errors in wt-loop and enter backoff/wait instead of stalling

### Modified Capabilities

## Impact

- `.claude/commands/wt/sentinel.md` — sentinel skill prompt (deference rules)
- `lib/loop/engine.sh` — API error detection, backoff logic, `waiting:api` status
- `bin/wt-loop` — new status constant
- `lib/orchestration/watchdog.sh` — recognize `waiting:api` as non-stall state
