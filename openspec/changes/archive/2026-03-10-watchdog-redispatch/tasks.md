## 1. State Schema

- [x] 1.1 Add `redispatch_count: 0` field to the per-change object in `init_state()` in `lib/orchestration/state.sh` (at the change level alongside `status`, `tokens_used`, not inside the `watchdog` sub-object)
- [x] 1.2 Add `max_redispatch` directive reading in `lib/orchestration/config.sh` or monitor.sh config loading (default: 2)

## 2. Redispatch Function

- [x] 2.1 Create `redispatch_change()` function in `lib/orchestration/dispatcher.sh` that: kills Ralph PID, calls `_watchdog_salvage_partial_work`, builds `retry_context` from failure pattern + partial diff file list + iteration count + tokens used, increments `redispatch_count`, cleans up old worktree (`wt-close` or `git worktree remove --force` + `git branch -D`), resets watchdog sub-object (escalation_level=0, hash ring cleared), sets change status to `pending`
- [x] 2.2 Verify existing retry_context injection in `dispatch_change()` works for redispatch (it already reads `retry_context` from state and injects it into proposals — just confirm it handles the watchdog-built context correctly)

## 3. Watchdog Escalation Chain

- [x] 3.1 Modify `_watchdog_escalate()` L3 case: check `redispatch_count < max_redispatch` — if yes, call `redispatch_change()`; if no, fall through to fail (existing L4+ behavior)
- [x] 3.2 Modify `_watchdog_check_progress()` spinning path: check `redispatch_count < max_redispatch` — if yes, call `redispatch_change()` instead of immediate `failed`; if no, keep existing fail behavior
- [x] 3.3 Emit `WATCHDOG_REDISPATCH` event with change name, redispatch count, failure pattern, and tokens used

## 4. Status Display

- [x] 4.1 Update status output in `lib/orchestration/monitor.sh` (or `state.sh` status functions) to show redispatch count for changes where `redispatch_count > 0` (e.g., "running (redispatch 1/2)")

## 5. Tests

- [x] 5.1 Add unit test: `redispatch_change()` increments `redispatch_count` and sets status to `pending`
- [x] 5.2 Add unit test: L3 escalation calls redispatch when count < max, fails when count >= max
- [x] 5.3 Add unit test: spinning detection calls redispatch when count < max, fails when count >= max
- [x] 5.4 Add unit test: `dispatch_change()` includes retry_context in proposal when present
- [x] 5.5 Add integration test: full cycle — dispatch → stuck detection → redispatch → second attempt runs
