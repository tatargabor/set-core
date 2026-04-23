## ADDED Requirements

### Requirement: Merger passes authoritative worktree path to set-merge

The merger SHALL invoke `set-merge` with an explicit `--worktree <path>` argument derived from `change.worktree_path`, so the merge script does not need to rediscover the worktree by name pattern.

#### Scenario: worktree_path is known
- **WHEN** `merge_change` runs for a change whose `Change.worktree_path` is a non-empty string pointing to an existing directory
- **THEN** the subprocess command SHALL be `["set-merge", <change_name>, "--no-push", "--ff-only", "--worktree", <worktree_path>]`

#### Scenario: worktree_path is missing
- **WHEN** `merge_change` runs for a change whose `Change.worktree_path` is empty or null
- **THEN** the subprocess command SHALL omit `--worktree` and fall back to `set-merge`'s name-based discovery
- **AND** a WARN log SHALL record that authoritative path was unavailable

#### Scenario: worktree_path points to a missing directory
- **WHEN** `Change.worktree_path` is set but the directory no longer exists
- **THEN** the merger SHALL log a WARN, then omit `--worktree` and let `set-merge` retry discovery
- **AND** if discovery also fails, the merge returns the existing "worktree not found" failure path unchanged

### Requirement: Persistent merge-stall circuit-breaker

The merger SHALL track FF-failure merge stalls per change in `change.extras["merge_stall_attempts"]`, distinct from the existing `ff_retry_count` (per-cycle) and `total_merge_attempts` (overall) counters. When the stall counter crosses a configurable threshold, the change SHALL be transitioned to `failed:merge_stalled` and escalated via `escalate_change_to_fix_iss` using `escalation_reason="merge_stalled"`.

#### Scenario: Stall counter increments on every FF failure
- **WHEN** `merge_change` ends with an FF-merge failure (status transitioned back through the re-integrate/retry path)
- **THEN** `change.extras["merge_stall_attempts"]` SHALL be incremented by 1 and persisted via `update_change_field`

#### Scenario: Successful merge resets the stall counter
- **WHEN** `merge_change` completes successfully (status="merged")
- **THEN** `change.extras["merge_stall_attempts"]` SHALL be cleared (removed or set to 0)

#### Scenario: State reset clears the stall counter
- **WHEN** a caller resets a change to pending via `reset_change_to_pending`
- **THEN** `change.extras["merge_stall_attempts"]` SHALL be cleared alongside the other gate-result extras
- **AND** a re-dispatched change SHALL begin with a fresh stall counter at 0

#### Scenario: Threshold crossed — escalate via fix-iss
- **WHEN** `merge_stall_attempts` reaches or exceeds the threshold (default 6, configurable via `state.extras["directives"]["merge_stall_threshold"]`)
- **THEN** the change status SHALL be set to `failed:merge_stalled`
- **AND** the change SHALL be removed from `state.merge_queue` so the orchestrator does not re-enqueue it
- **AND** `escalate_change_to_fix_iss` SHALL be called with keyword arguments `state_file=<state_file>`, `change_name=<name>`, `stop_gate="merge"`, `escalation_reason="merge_stalled"`, `event_bus=<bus>`
- **AND** the function SHALL internally register an issue with source `circuit-breaker:merge_stalled` (derived from `escalation_reason`) and affected_change equal to the change name

#### Scenario: Threshold respects directive override
- **WHEN** `state.extras.get("directives", {}).get("merge_stall_threshold")` is a positive integer N
- **THEN** escalation SHALL trigger at the Nth failure instead of the default
- **WHEN** the directive is missing, zero, or `state.extras` has no `directives` key
- **THEN** the default threshold (6) SHALL apply without raising KeyError

### Requirement: Circuit-breaker logs before escalation

When the circuit-breaker fires, the merger SHALL log ERROR with the change name, cumulative attempt count, and the most recent merge failure's stdout/stderr head, so post-mortem analysis has a single log entry to find.

#### Scenario: Escalation log line
- **WHEN** the circuit-breaker fires for change "foo" at attempt 20
- **THEN** a single ERROR-level log entry SHALL include: change name, attempt count, last exit code, first 500 chars of stdout, first 500 chars of stderr
- **AND** the log SHALL be emitted BEFORE `escalate_change_to_fix_iss` is called
