## Purpose

Migrate `lib/orchestration/watchdog.sh` (424 LOC) to `lib/set_orch/watchdog.py`. The watchdog monitors per-change health during orchestration — detecting timeouts, action hash loops, and escalating stuck changes through restart → redispatch → fail levels.

## Requirements

### WATCH-01: Per-Change Timeout Detection
- `watchdog_check(change, state)` evaluates a single change's health
- Timeout thresholds per state: running=600s, verifying=300s, dispatched=120s
- Thresholds overridable via `watchdog_timeout` directive in orchestration.yaml
- Return `WatchdogResult(action, reason)` — action is one of: ok, restart, redispatch, fail

### WATCH-02: Action Hash Loop Detection
- Track last N action hashes per change (ring buffer, size=5)
- `detect_hash_loop(hash_ring)` returns True if all hashes are identical
- Consecutive same-hash threshold: 5 (configurable via `WATCHDOG_LOOP_THRESHOLD`)
- Loop detection triggers escalation independent of timeout

### WATCH-03: Escalation Levels
- Level 0: OK — no action needed
- Level 1: Restart — kill and restart the change's agent
- Level 2: Redispatch — close worktree, create fresh, redispatch
- Level 3: Fail — mark change as failed, emit event
- Each escalation increments `escalation_level` in change state
- Escalation resets on genuine progress (new files, test results)

### WATCH-04: Progress Baseline Tracking
- `watchdog_init_state(change)` creates initial baseline: file count, test count, iteration number
- Progress detected by comparing current vs baseline metrics
- Genuine progress resets escalation level and timeout timer

### WATCH-05: State Storage
- Watchdog state stored in `orchestration-state.json` under `.changes[].watchdog`
- Fields: `last_activity_epoch`, `action_hash_ring[]`, `consecutive_same_hash`, `escalation_level`, `progress_baseline`
- Read/write via existing `state.py` functions

### WATCH-06: CLI Subcommands
- `set-orch-core watchdog check --change <name>` — run watchdog check for one change
- `set-orch-core watchdog status` — show watchdog state for all active changes
- Registered in `cli.py` under `watchdog` group

### WATCH-07: Unit Tests
- Test timeout detection with mocked timestamps
- Test hash loop detection with various ring patterns
- Test escalation progression and reset
- Test progress baseline comparison
