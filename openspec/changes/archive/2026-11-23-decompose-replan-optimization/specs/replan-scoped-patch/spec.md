## ADDED Requirements

<!--
IN SCOPE:
- Joiner-style scoped replan path that emits a `{add, remove, modify}` patch instead of a full plan.
- Patch schema, atomic-application semantics, and validator.
- Stall counter that bounds unproductive replan loops.
- Fallback to full replan when patch validation fails.
- Directive `replan_strategy: scoped_patch | full` and `max_consecutive_replans_without_progress`.

OUT OF SCOPE:
- Initial plan generation (`run_planning_pipeline()` first run is full plan; this spec covers replan only).
- Patch generation by anything other than the planner (no manual edit endpoint in this spec).
- Cross-spec patches.
-->

### Requirement: Scoped replan emits plan patches
When `replan_strategy: scoped_patch` is configured AND a replan is triggered, the planner SHALL emit a JSON patch object with operations describing additions, removals, and modifications to the existing plan, rather than a full new plan.

#### Scenario: Patch shape on scoped replan
- **WHEN** `_handle_auto_replan` is called with `replan_strategy=scoped_patch`
- **THEN** the planner SHALL invoke a scoped-patch Claude prompt that returns JSON of shape `{"patch_version": 1, "base_plan_version": <int>, "operations": [...], "reasoning": "..."}`
- **AND** each operation SHALL be one of `{"op": "add", "change": {...}}`, `{"op": "remove", "name": "<change-name>"}`, `{"op": "modify", "name": "<change-name>", "fields": {...}}`

#### Scenario: Initial plan unaffected
- **WHEN** the planner runs the initial decompose (no prior plan exists)
- **THEN** it SHALL produce a full plan (not a patch), regardless of `replan_strategy`

### Requirement: Patch validation rejects invalid operations
The system SHALL validate every patch before applying it. The patch SHALL be rejected when any of the following hold: a `remove` targets a change with status `merged` or `running`; an `add` introduces a name that already exists; a `modify` targets a change with status `merged`; an operation references a name not present in the plan (for `modify`/`remove`); or `base_plan_version` does not match the current `plan_version`.

#### Scenario: Reject removal of merged change
- **WHEN** a patch contains `{"op": "remove", "name": "auth-foundation"}` and `auth-foundation.status == "merged"`
- **THEN** the patch SHALL be rejected
- **AND** the orchestrator SHALL fall back to the full replan path
- **AND** the rejection SHALL emit a `PATCH_REJECTED` event with reason `"remove of merged change"`

#### Scenario: Reject duplicate add
- **WHEN** a patch contains `{"op": "add", "change": {"name": "X", ...}}` and a change named `X` already exists in the plan
- **THEN** the patch SHALL be rejected with reason `"duplicate add"`

#### Scenario: Reject stale base version
- **WHEN** a patch declares `base_plan_version: 5` and the current `plan_version` is 7
- **THEN** the patch SHALL be rejected with reason `"stale base_plan_version"`

### Requirement: Patch application is atomic under state lock
The orchestrator SHALL apply a validated patch atomically: acquire the state lock, apply all operations sequentially, increment `plan_version`, persist, release lock. Partial application is forbidden.

#### Scenario: Atomic patch application
- **WHEN** a validated patch with N operations is applied
- **THEN** the orchestrator SHALL hold the state lock for the entire apply sequence
- **AND** SHALL increment `plan_version` exactly once
- **AND** SHALL emit a single `PLAN_PATCHED` event with the operation count after persisting

#### Scenario: Mid-apply error rolls back
- **WHEN** an operation in the patch raises an exception during apply
- **THEN** the orchestrator SHALL roll back any prior operations in the same patch
- **AND** SHALL leave the state file unchanged
- **AND** SHALL emit a `PATCH_FAILED` event with the failing operation index

### Requirement: Fallback to full replan on patch failure
The orchestrator SHALL fall back to the full-replan code path when the patch is rejected by validation OR fails to apply.

#### Scenario: Validation rejection triggers full replan
- **WHEN** a patch is rejected by the validator
- **THEN** the orchestrator SHALL invoke `_auto_replan_cycle()` (full replan) with the same trigger context
- **AND** the LLM cost of both calls SHALL be observable per cycle

### Requirement: Stall counter bounds unproductive replans
The system SHALL maintain a `replan_stall_count` integer state field. After each replan cycle: if the resulting patch (or new plan) contains at least one `add` operation AND the total operation count is greater than 1, the counter SHALL reset to 0; otherwise it SHALL increment by 1. The counter SHALL also reset on any `CHANGE_MERGED` event.

#### Scenario: Productive replan resets counter
- **WHEN** a replan applies a patch with `operations=[{op: "add", ...}, {op: "modify", ...}]`
- **THEN** `replan_stall_count` SHALL be set to 0

#### Scenario: Unproductive replan increments counter
- **WHEN** a replan applies a patch with `operations=[{op: "modify", ...}]` only (no add)
- **THEN** `replan_stall_count` SHALL be incremented by 1

#### Scenario: Merge resets counter
- **WHEN** a `CHANGE_MERGED` event fires
- **THEN** `replan_stall_count` SHALL be reset to 0 in the same state-lock window as the merge

### Requirement: Stall halts replan at threshold
When `replan_stall_count >= max_consecutive_replans_without_progress` AND the directive value is greater than 0, the orchestrator SHALL stop further replans, set status to `replan_stalled`, and require operator acknowledgment to resume.

#### Scenario: Stall threshold reached
- **WHEN** `max_consecutive_replans_without_progress = 2` AND `replan_stall_count = 2`
- **THEN** the orchestrator SHALL set status to `replan_stalled`
- **AND** SHALL emit a sentinel finding of type `REPLAN_STALL` with severity `warning`
- **AND** SHALL NOT trigger any further replan until acknowledged

#### Scenario: Stall counter disabled by default
- **WHEN** `max_consecutive_replans_without_progress = 0`
- **THEN** the stall halt SHALL never fire regardless of `replan_stall_count` value

#### Scenario: Operator acknowledgment resumes replan
- **WHEN** an operator POSTs the stall-acknowledgment endpoint while status is `replan_stalled`
- **THEN** status SHALL transition to `running`
- **AND** `replan_stall_count` SHALL reset to 0
