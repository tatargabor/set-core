# Supervisor Transition Triggers Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Transition-based anomaly triggers (not steady-state)
The supervisor daemon's anomaly detectors that read `change.status` from `orchestration-state.json` SHALL fire ONLY on status TRANSITIONS, never on steady-state values. A change that entered `failed` five minutes ago and has not moved since SHALL NOT re-fire its `integration_failed` trigger on every subsequent poll.

Affected detectors in `lib/set_orch/supervisor/anomaly.py`:
- `detect_integration_failed` — reads `change.status` and matches any substring containing `"failed"`
- `detect_terminal_state` — reads `state.status` and matches `TERMINAL_STATUSES`
- `detect_token_stall` — reads per-change `tokens_used` + `change.status` and, once the threshold is crossed, currently fires every poll

The existing `detect_process_crash`, `detect_state_stall`, `detect_error_rate_spike`, and `detect_log_silence` detectors already use timestamp-based thresholds and are transition-free — they are NOT affected.

#### Scenario: Status first transitions to failed
- **WHEN** the supervisor poll observes `foundation-setup.status` change from `integrating` to `failed` (a new value compared to the last observed status for that change)
- **THEN** `detect_integration_failed` emits one `integration_failed` trigger for `foundation-setup`
- **THEN** the trigger executor dispatches an ephemeral Claude per the normal retry budget

#### Scenario: Status remains failed across polls
- **WHEN** the next supervisor poll observes `foundation-setup.status` still equals `failed` (no transition)
- **THEN** `detect_integration_failed` emits NO trigger for `foundation-setup`
- **THEN** no `SUPERVISOR_TRIGGER` event (neither a real dispatch nor a `skipped: retry_budget_exhausted` record) is written for this change
- **THEN** the supervisor.events.jsonl remains free of repeated entries for the same steady-state failure

#### Scenario: Status transitions back out of failed then back in
- **WHEN** `foundation-setup.status` goes `failed → done → failed` across three polls
- **THEN** the second `failed` is a new transition from the supervisor's view and re-fires `integration_failed`
- **THEN** this consumes a fresh unit from the retry budget only if the budget tracks (trigger, change) attempts (which it already does via `SupervisorStatus.trigger_attempts`)

### Requirement: Per-change last-observed-status in SupervisorStatus
The system SHALL add a `last_change_statuses: dict[str, str]` field to `SupervisorStatus` that records the most recently observed status for each change name the supervisor has seen. The field is persisted in `.set/supervisor/status.json` so a daemon restart does not re-fire triggers for changes that were already in a terminal/failed state at the time of restart.

#### Scenario: Daemon restart mid-run with a pre-existing failed change
- **WHEN** the daemon is killed while `foundation-setup.status = failed` AND the supervisor had already fired its 3 `integration_failed` triggers before the kill
- **WHEN** the daemon restarts and the first poll reads the same `failed` status from `orchestration-state.json`
- **THEN** `last_change_statuses["foundation-setup"]` is read from the persisted `status.json` as `"failed"`
- **THEN** no transition is observed and no new trigger fires
- **THEN** the supervisor is a quiet no-op for this change until the user actively changes the status

#### Scenario: Fresh daemon sees a change for the first time
- **WHEN** the daemon starts and observes a change it has never seen before (not present in `last_change_statuses`)
- **THEN** the first observed status IS treated as a transition (from "unseen" to whatever the current value is)
- **THEN** if the current status already matches a trigger condition (e.g., `failed`), the trigger fires exactly once on this first observation

### Requirement: Transition detection for non-change-scoped triggers
The system SHALL track orchestration-level transitions for `detect_terminal_state` the same way: once `state.status` has been observed as terminal AND the daemon has dispatched its one `terminal_state` trigger, no repeat firing on subsequent polls.

#### Scenario: Orchestration in terminal state across multiple polls
- **WHEN** `state.status = done` on poll N, terminal_state trigger fires and the daemon's shutdown path is entered
- **WHEN** the daemon restarts (for any reason) after the orchestration has already been marked `done`
- **THEN** `detect_terminal_state` observes the same `done` status, but `SupervisorStatus.trigger_attempts["terminal_state"] >= 1` causes the trigger to be skipped
- **THEN** the daemon emits `SUPERVISOR_STOP` with reason `orchestrator_already_terminal` and exits without spawning another final-report Claude

### Requirement: Token-stall detector transition-aware
The system SHALL treat `detect_token_stall` as transition-based too: once a change has crossed the `DEFAULT_TOKEN_STALL_LIMIT` AND stalled past `DEFAULT_TOKEN_STALL_SECS`, the trigger fires once. Subsequent polls do not re-fire until the change either (a) moves its state or (b) the supervisor re-observes a `tokens_used` increase that does not correlate with progress.

#### Scenario: Change stuck at 600k tokens with no state movement
- **WHEN** poll N observes `foundation-setup.tokens_used = 600000 AND state.last_mtime is 30 minutes old`
- **THEN** `detect_token_stall` fires once
- **WHEN** poll N+1 observes the same numbers (unchanged)
- **THEN** `detect_token_stall` does NOT re-fire
