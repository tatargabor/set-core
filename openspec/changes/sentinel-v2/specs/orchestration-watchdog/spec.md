# Orchestration Watchdog

Self-healing watchdog integrated into the orchestration monitor loop. Detects stuck changes, stalled orchestrators, and runaway loops — then takes corrective action via an escalation chain.

## Requirements

### R1: Per-State Timeout Detection
- Track last activity epoch per change (loop-state.json mtime or state transition timestamp)
- Configurable timeout per status: `running` (600s default), `verifying` (300s), `dispatched` (120s)
- Only trigger when the Ralph PID is also dead (alive PID = long iteration, not stale)
- Timeout triggers escalation (R4)

### R2: Action Hash Loop Detection
- Each poll cycle, compute hash of observable change state: `(loop-state mtime, tokens_used, ralph_status)`
- Maintain a ring buffer of last N hashes per change (default N=5)
- If `watchdog_loop_threshold` (default 5) consecutive hashes are identical, the change is stuck
- Stuck detection triggers escalation (R4)

### R3: Orchestrator Self-Liveness
- Emit a `WATCHDOG_HEARTBEAT` event to `orchestration-events.jsonl` every poll cycle
- The sentinel monitors events.jsonl mtime to detect alive-but-stuck orchestrator
- If no event emitted for `sentinel_stuck_timeout` (default 180s), sentinel intervenes

### R4: Escalation Chain
- Level 0: Normal operation
- Level 1: Log warning + emit `WATCHDOG_WARN` event
- Level 2: Call `resume_change()` + emit `WATCHDOG_RESUME` event
- Level 3: Kill Ralph PID + call `resume_change()` + emit `WATCHDOG_KILL` event
- Level 4: Mark change as `failed` + emit `WATCHDOG_FAILED` event + send notification
- Escalation level persists per change across poll cycles
- Successful activity (state change, new tokens) resets escalation to level 0

### R5: Watchdog State Storage
- Per-change watchdog state stored in `orchestration-state.json` under a `watchdog` sub-object
- Fields: `last_activity_epoch`, `action_hash_ring`, `consecutive_same_hash`, `escalation_level`
- Initialized lazily on first watchdog check

### R6: Configuration
- `watchdog_timeout`: Per-state timeout in seconds (default: 600)
- `watchdog_loop_threshold`: Consecutive identical hashes before escalation (default: 5)
- Both configurable via `orchestration.yaml` directives
