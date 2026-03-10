## MODIFIED Requirements

### R4: Escalation Chain
- Level 0: Normal operation
- Level 1: Log warning + emit `WATCHDOG_WARN` event
- Level 2: Call `resume_change()` + emit `WATCHDOG_RESUME` event
- Level 3: If `redispatch_count < max_redispatch`: kill Ralph PID + salvage partial work + cleanup worktree + build retry_context + set status to `pending` + increment `redispatch_count` + emit `WATCHDOG_REDISPATCH` event. If `redispatch_count >= max_redispatch`: salvage partial work + mark change as `failed` + emit `WATCHDOG_FAILED` event + send notification
- Level 4+: Same as L3 when redispatch exhausted — salvage + fail + notify
- Escalation level persists per change across poll cycles
- Successful activity (state change, new tokens) resets escalation to level 0

#### Scenario: L3 redispatch when attempts remain
- **WHEN** escalation reaches level 3 AND `redispatch_count` is less than `max_redispatch`
- **THEN** the system SHALL kill Ralph, salvage work, cleanup worktree, reset to `pending`, increment `redispatch_count`, and emit `WATCHDOG_REDISPATCH`

#### Scenario: L3 fail when redispatch exhausted
- **WHEN** escalation reaches level 3 AND `redispatch_count` equals or exceeds `max_redispatch`
- **THEN** the system SHALL salvage work, mark as `failed`, emit `WATCHDOG_FAILED`, and send notification

### R5: Watchdog State Storage
- Per-change watchdog state stored in `orchestration-state.json` under a `watchdog` sub-object
- Fields: `last_activity_epoch`, `action_hash_ring`, `consecutive_same_hash`, `escalation_level`, `progress_baseline`
- Initialized lazily on first watchdog check
- The `redispatch_count` field is stored at the change level (not inside `watchdog`), alongside `status`, `tokens_used`, etc.

#### Scenario: Watchdog state reset on redispatch
- **WHEN** a change is re-dispatched
- **THEN** the watchdog sub-object SHALL be reset (escalation_level=0, hash ring cleared, progress_baseline=0)

### R7: Progress-Based Trend Detection
- Reads completed iterations from loop-state.json
- **Spinning**: 3+ consecutive no_op iterations with no commits — if `redispatch_count < max_redispatch`: redispatch; else: fail
- **Stuck**: 3+ consecutive iterations without commits (but not all no_op) — pause (unchanged)
- TOCTOU guard: re-read loop-state status before taking action

#### Scenario: Spinning triggers redispatch when attempts remain
- **WHEN** spinning pattern detected AND `redispatch_count` is less than `max_redispatch`
- **THEN** the system SHALL kill Ralph, salvage work, cleanup worktree, reset to `pending`, and increment `redispatch_count`

#### Scenario: Spinning triggers fail when redispatch exhausted
- **WHEN** spinning pattern detected AND `redispatch_count` equals or exceeds `max_redispatch`
- **THEN** the system SHALL salvage work and mark the change as `failed`

### R6: Configuration
- `watchdog_timeout`: Per-state timeout in seconds (default: 600)
- `watchdog_loop_threshold`: Consecutive identical hashes to detect stuck (default: 5)
- `max_redispatch`: Maximum re-dispatch attempts per change (default: 2)

#### Scenario: max_redispatch directive respected
- **WHEN** `max_redispatch` is set to N in orchestration.yaml directives
- **THEN** the watchdog SHALL allow up to N redispatch attempts per change before failing
