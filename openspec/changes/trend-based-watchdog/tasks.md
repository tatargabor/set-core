## 1. Remove per-change token budget enforcement

- [x] 1.1 Delete `_watchdog_check_token_budget()` function from `lib/orchestration/watchdog.sh`
- [x] 1.2 Delete `_watchdog_token_limit_for_change()` function from `lib/orchestration/watchdog.sh`
- [x] 1.3 Remove the `_watchdog_check_token_budget "$change_name"` call at the end of `watchdog_check()`
- [x] 1.4 Remove the `WATCHDOG_MAX_TOKENS_PER_CHANGE` variable and its comment from `watchdog.sh`
- [x] 1.5 Remove the `WATCHDOG_MAX_TOKENS_PER_CHANGE` directive assignment from `monitor.sh` (the `max_tokens_per_change` directive read)
- [x] 1.6 Remove the done-check guard block (`if pct >= 100` + loop-state re-read) — will be reimplemented in the new progress check

## 2. Implement progress-based trend detection

- [x] 2.1 Add `_watchdog_check_progress()` function to `lib/orchestration/watchdog.sh` that reads loop-state.json iterations array
- [x] 2.2 Implement status guard: re-read change status from state, return early if already `failed`, `paused`, or `waiting:budget` (prevents double-fire with escalation chain)
- [x] 2.3 Implement done guard: return early if loop-state status is `"done"`
- [x] 2.4 Implement minimum iterations guard: return early if fewer than 2 completed iterations
- [x] 2.5 Implement progress baseline guard: on resume, `resume_change()` stores current iteration count in `watchdog.progress_baseline`. Only examine iterations with `n` > baseline.
- [x] 2.6 Implement spinning detection: 3+ consecutive tail iterations (after baseline) with `no_op=true` AND `commits=[]` → fail the change
- [x] 2.7 Implement stuck detection: 3+ consecutive tail iterations (after baseline) with `commits=[]` (but not all no_op) → pause the change
- [x] 2.8 Add TOCTOU guard: re-read loop-state status immediately before calling `pause_change()` or setting `"failed"`, skip if `"done"`
- [x] 2.9 Emit `WATCHDOG_NO_PROGRESS` events with pattern and action fields
- [x] 2.10 Add the `_watchdog_check_progress "$change_name"` call at the end of `watchdog_check()` (replacing the old budget call site)

## 3. Update resume_change() for progress baseline

- [x] 3.1 In `resume_change()` in `dispatcher.sh`, read current iteration count from loop-state and store as `watchdog.progress_baseline` in the change's watchdog state

## 4. Verify global safety nets remain intact

- [x] 4.1 Verify `monitor.sh` token_budget dispatch throttle is unchanged and functional
- [x] 4.2 Verify `monitor.sh` token_hard_limit checkpoint trigger is unchanged and functional
- [x] 4.3 Verify the safety-net poll of suspended changes for done loop-state is unchanged

## 5. Update comments and documentation

- [x] 5.1 Update the comment block at the top of the watchdog budget section to describe the new progress-based approach
- [x] 5.2 Remove references to "S=2M, M=5M, L=10M, XL=20M" complexity defaults from any comments
