## ADDED Requirements

### Requirement: Single-handler path for stuck fix-loop exits with new commits
When the agent loop exits with `loop_status=stuck` AND at least one new commit since the loop started, the engine SHALL re-dispatch the change through the verify-gate pipeline directly on the next monitor poll. The verifier SHALL NOT mark the change `stalled` in this case.

Prior behavior (to be removed): the engine logged `routing to re-gate (skip stall timeout)` and the verifier simultaneously logged `Change <name> stuck — marking stalled for watchdog`, writing `status=stalled`. The watchdog then auto-recovered after 300s, the agent ran briefly, exited stuck, and the loop repeated. This caused 23 cycles on `craftbrew-run-20260418-1719::promotions-engine` with zero progress.

#### Scenario: Stuck exit with new commits re-enters gate
- **WHEN** `ralph_status=stuck` and `new_commits_since_dispatch > 0`
- **THEN** `engine._handle_agent_exit()` SHALL call `verifier.run_verify_pipeline(change)` directly
- **AND** `verifier` SHALL NOT write `change.status=stalled` on this path
- **AND** the log line `marking stalled for watchdog` SHALL NOT be emitted

#### Scenario: Stuck exit with no new commits stalls normally
- **WHEN** `ralph_status=stuck` and `new_commits_since_dispatch == 0`
- **THEN** the verifier SHALL set `change.status=stalled` (current behavior)
- **AND** the watchdog's 300s recovery timer applies

### Requirement: Verifier stale-detection branch checks commit progress
The verifier code path that handles `ralph_status ∈ {stopped, stalled, stuck}` by writing `status=stalled` SHALL additionally check `git log <branch> --since <stalled_at>` before writing. If new commits exist since the last observed `stalled_at` (or since dispatch if never stalled), the branch SHALL skip the stall write and return control to the engine's re-gate path.

#### Scenario: Stale-detection observes new commits
- **WHEN** the verifier's stale branch fires with `stalled_at=T0` and the worktree has commits dated > T0
- **THEN** the function SHALL log `Skipping stall write: <N> new commits since <T0>` at DEBUG
- **AND** SHALL NOT call `state.update(<change>.status='stalled')`
- **AND** SHALL return without emitting a stall event

### Requirement: Stuck-loop circuit breaker
A per-change counter `stuck_loop_count` SHALL track consecutive `loop_status=stuck` exits that re-entered the gate with the SAME `last_gate_fingerprint` (see `orchestration-token-tracking` spec delta for the fingerprint's single-writer contract — it is written only by the verifier). When `stuck_loop_count` reaches `MAX_STUCK_LOOPS` (default 3, configurable via directive `max_stuck_loops`), the engine SHALL fail the change with `status=failed:stuck_no_progress` and surface it to the investigation pipeline.

The threshold check SHALL happen BEFORE the reset evaluation in the same poll iteration: if the incoming count would simultaneously reach the threshold AND the fingerprint has changed, the threshold does NOT fire and the counter resets to 0 instead.

#### Scenario: Counter increments on identical fingerprint
- **WHEN** a change re-enters the gate after `loop_status=stuck` and the resulting `VERIFY_GATE` event has the same `stop_gate` and `finding_fingerprint` as the previous one
- **THEN** `stuck_loop_count` SHALL be incremented by 1
- **AND** the count SHALL be persisted to state

#### Scenario: Counter resets on progress
- **WHEN** a change re-enters the gate after `loop_status=stuck` and the new `last_gate_fingerprint` differs from the previous one
- **THEN** `stuck_loop_count` SHALL be reset to 0 (no threshold fires this poll)

#### Scenario: Max stuck loops triggers hard fail
- **WHEN** `stuck_loop_count >= max_stuck_loops` AND the new fingerprint matches the previous (no progress)
- **THEN** the engine SHALL set `change.status=failed:stuck_no_progress`
- **AND** SHALL write a structured event `STUCK_LOOP_ESCALATED` with fields `{change, stop_gate, finding_fingerprint, count}`
- **AND** SHALL trigger the investigation/fix-iss pipeline (see `investigation-runner` spec delta)

### Requirement: Verify pipeline honors per-gate retry policy
On a retry invocation of `run_verify_pipeline()`, the pipeline SHALL consult the active profile's `gate_retry_policy()` (see `gate-retry-policy` spec delta) for each gate in the active set and route execution accordingly:

- `"always"` gates run unchanged.
- `"cached"` gates invoke cache-reuse-or-invalidate logic and may skip actual execution, emitting `GATE_CACHED` if reused.
- `"scoped"` gates compute their filtered subset via `gate_scope_filter()` and either run the subset or fall through to `"cached"` behavior if no overlap.

Whether a pipeline run is a "retry" SHALL be determined by `change.verify_retry_index > 0`. The FIRST verify run on a change is NEVER treated as a retry (cache is always cold on the first run).

#### Scenario: First verify run ignores retry policy
- **WHEN** `verify_retry_index == 0` (first-ever verify on this change)
- **THEN** every gate in the active set SHALL run fully regardless of declared retry policy
- **AND** no `GATE_CACHED` events SHALL be emitted

#### Scenario: Second verify run applies retry policy
- **WHEN** `verify_retry_index == 1` (first retry)
- **THEN** each gate's declared retry policy SHALL be consulted and applied
- **AND** gates with `policy="always"` SHALL run fully
- **AND** gates with `policy="cached"` SHALL reuse or invalidate per `gate-retry-policy` rules

### Requirement: Aggregate retry wall-time budget
The verify pipeline SHALL track cumulative retry wall time per change as `change.retry_wall_time_ms`. If this value exceeds `max_retry_wall_time_ms` (default `1_800_000` i.e. 30 min) for any single change, the verifier SHALL emit a `RETRY_WALL_TIME_EXHAUSTED` event and escalate the change to the fix-iss pipeline with `escalation_reason="retry_wall_time_exhausted"`.

This guards against the "slow death" failure mode where individual retries pass budget checks but cumulatively burn hours.

#### Scenario: Wall-time budget tripped on 5th retry
- **WHEN** a change's cumulative `retry_wall_time_ms` reaches `1,850,000` after its 5th retry
- **THEN** the verifier SHALL emit `RETRY_WALL_TIME_EXHAUSTED` with `{change, cumulative_ms, retry_count}`
- **AND** set `change.status = "failed:retry_wall_time_exhausted"`
- **AND** invoke `escalate_change_to_fix_iss(..., escalation_reason="retry_wall_time_exhausted")`

#### Scenario: Wall-time budget never tripped on fast retries
- **WHEN** a change goes through 5 retries each taking 60s (total 300s)
- **THEN** no `RETRY_WALL_TIME_EXHAUSTED` SHALL fire (under 30 min)

### Requirement: stuck_loop_count state field
`orchestration-state.json`'s per-change dict SHALL gain `stuck_loop_count: int` (default 0). Backwards-compatible with old states lacking the field.

#### Scenario: Old state file loads without stuck_loop_count
- **WHEN** an `orchestration-state.json` without `stuck_loop_count` is loaded
- **THEN** the loader SHALL populate the field as `0` on each change
