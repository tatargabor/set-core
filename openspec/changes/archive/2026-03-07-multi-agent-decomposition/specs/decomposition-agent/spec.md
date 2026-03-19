## ADDED Requirements

### Requirement: Agent-based planning path in cmd_plan

The orchestrator SHALL support an agent-based planning method alongside the existing API-based method. When directive `plan_method` is set to `"agent"`, `cmd_plan()` SHALL create a planning worktree, dispatch a Ralph loop with the decomposition skill, and collect the resulting `orchestration-plan.json`.

#### Scenario: Agent-based decomposition with plan_method directive
- **WHEN** `plan_method: agent` is set in orchestration config
- **AND** `set-orchestrate plan --spec <path>` is invoked
- **THEN** a planning worktree named `wt-planning-v{N}` SHALL be created
- **AND** a Ralph loop SHALL be dispatched with the decomposition skill as task description
- **AND** the orchestrator SHALL wait for the Ralph loop to complete
- **AND** the resulting `orchestration-plan.json` SHALL be copied from the planning worktree to the project root
- **AND** the planning worktree SHALL be cleaned up after successful extraction

#### Scenario: Fallback to API method on agent failure
- **WHEN** `plan_method: agent` is set
- **AND** the agent planning fails (timeout, invalid JSON, validation failure)
- **THEN** the orchestrator SHALL log a warning with the failure reason
- **AND** SHALL fall back to the existing API-based planning method
- **AND** the planning worktree SHALL be cleaned up

#### Scenario: Default plan_method is api
- **WHEN** no `plan_method` directive is specified
- **THEN** `cmd_plan()` SHALL use the existing API-based planning (current behavior unchanged)

### Requirement: Plan metadata fields

The `orchestration-plan.json` output SHALL include `plan_phase` and `plan_method` fields to identify how and when a plan was created.

#### Scenario: Initial plan metadata
- **WHEN** `cmd_plan()` generates a plan (first time, no prior plan)
- **THEN** the plan JSON SHALL include `"plan_phase": "initial"` and `"plan_method": "api"` or `"agent"` matching the method used

#### Scenario: Iteration plan metadata
- **WHEN** `auto_replan_cycle()` generates a plan
- **THEN** the plan JSON SHALL include `"plan_phase": "iteration"` and the `plan_method` matching the method used
- **AND** `replan_cycle` SHALL continue to be tracked in state as before

#### Scenario: Backward compatibility
- **WHEN** an existing `orchestration-plan.json` lacks `plan_phase` or `plan_method` fields
- **THEN** the orchestrator SHALL treat missing `plan_phase` as `"initial"` and missing `plan_method` as `"api"`

### Requirement: Planning worktree lifecycle

The planning worktree SHALL follow a defined lifecycle managed by the orchestrator.

#### Scenario: Planning worktree creation
- **WHEN** agent-based planning is triggered
- **THEN** a worktree SHALL be created via `wt-new wt-planning-v{N}`
- **AND** the spec file SHALL be accessible in the worktree (via git)
- **AND** orchestration context (config, knowledge, requirements) SHALL be available

#### Scenario: Planning worktree monitoring
- **WHEN** a planning worktree is active
- **THEN** the sentinel SHALL monitor it the same way as change worktrees
- **AND** token tracking SHALL apply with a planning-specific budget (default 500K)

#### Scenario: Planning worktree cleanup
- **WHEN** the planning Ralph loop completes successfully
- **AND** `orchestration-plan.json` has been extracted and validated
- **THEN** the planning worktree SHALL be removed via `wt-close`
