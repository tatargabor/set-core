## ADDED Requirements

### Requirement: Replan strategy directive
The orchestrator SHALL honor a directive `replan_strategy` with values `full` or `scoped_patch` (default `full` until validated). The value selects whether `_handle_auto_replan()` invokes the full-decompose path or the scoped-patch path defined in capability `replan-scoped-patch`.

#### Scenario: Default strategy is full
- **WHEN** no `replan_strategy` is configured
- **THEN** `_handle_auto_replan()` SHALL call `_auto_replan_cycle()` (full replan)

#### Scenario: Scoped patch strategy
- **WHEN** `replan_strategy: scoped_patch` is configured
- **THEN** `_handle_auto_replan()` SHALL invoke the scoped-patch replan path
- **AND** SHALL fall back to the full path if patch validation fails (see `replan-scoped-patch`)

### Requirement: Replan reuses saved domain plans
On replan in the parallel path, the system SHALL invoke the domain-plan-reuse logic defined in capability `replan-domain-plan-reuse` before invoking Phase 2. Only domains whose input hash differs from the saved hash SHALL be re-decomposed.

#### Scenario: Single-domain change replans only that domain
- **WHEN** a replan fires after a single change (in domain `cart`) merged AND `domains-plans-<lineage>.json` exists
- **THEN** only domains whose hash changed (typically `cart` plus any cross-cutting domains affected by the brief) SHALL be re-decomposed
- **AND** the reuse SHALL be reported via a `REPLAN_REUSE` event

#### Scenario: Replan in serial mode reuses prior plan when stable
- **WHEN** the resolved strategy is `serial` AND the digest input hash equals the prior plan's input hash AND `replan_ctx.completed` is empty
- **THEN** the system SHALL skip the Claude call and reuse the prior `orchestration-plan.json`
- **AND** SHALL NOT emit a decompose `LLM_CALL` event

### Requirement: Event-driven post-merge scoped replan trigger
When `replan_strategy: scoped_patch` AND a `CHANGE_MERGED` event fires AND there is at least one pending change with the merged change in its `depends_on`, the orchestrator SHALL invoke a scoped-patch replan call against the downstream changes synchronously inside the merge handler before releasing the merge queue lock.

#### Scenario: Downstream change replanned post-merge
- **WHEN** change `auth-foundation` merges AND change `user-profile` has `depends_on: ["auth-foundation"]` AND is pending
- **AND** `replan_strategy: scoped_patch` is configured
- **THEN** the merge handler SHALL invoke a scoped-patch call with `target_changes: ["user-profile"]` before releasing the merge queue lock
- **AND** the call SHALL run on the main monitor loop, not in a thread

#### Scenario: No downstream changes — no replan
- **WHEN** a change merges AND no pending change has it in `depends_on`
- **THEN** no post-merge scoped replan SHALL be invoked

## MODIFIED Requirements

### Requirement: Python replan respects cycle limits
The Python replan SHALL enforce the same cycle limits and retry logic as bash. Additionally, the replan SHALL respect the stall counter `replan_stall_count` and the `max_consecutive_replans_without_progress` directive defined in capability `replan-scoped-patch`. When the stall threshold is reached, the orchestrator SHALL halt replan attempts and require operator acknowledgment.

#### Scenario: Cycle limit reached
- **WHEN** replan cycle count reaches `max_replan_cycles`
- **THEN** the engine SHALL mark status as "done" with `replan_limit_reached: true`
- **AND** SHALL NOT attempt further replanning

#### Scenario: Replan failure with retry
- **WHEN** a replan attempt fails (Claude error, validation failure)
- **THEN** the engine SHALL increment `replan_attempt` counter
- **AND** retry after 30 second delay
- **AND** give up after `MAX_REPLAN_RETRIES` consecutive failures

#### Scenario: Stall threshold reached
- **WHEN** `replan_stall_count >= max_consecutive_replans_without_progress > 0`
- **THEN** the engine SHALL set status to `replan_stalled`
- **AND** SHALL NOT attempt further replans until the stall is acknowledged
- **AND** SHALL emit a sentinel finding of type `REPLAN_STALL`
