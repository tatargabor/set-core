## ADDED Requirements

### Requirement: Planner assigns phase numbers to changes
The decompose prompt SHALL instruct the LLM to assign a `phase` integer (1..N) to each change. Phase assignment SHALL follow this ordering: infrastructure/schema/foundational → phase 1, feature changes → phases 2..N-1 grouped by domain coherence, cleanup-after → last phase. The planner SHALL create between 2 and 5 phases. The `phase` field SHALL appear in the plan JSON output schema.

#### Scenario: Standard decomposition with phases
- **WHEN** the planner decomposes a spec with 10+ changes
- **THEN** each change in the plan JSON SHALL have a `phase` field with an integer value between 1 and N (where N <= 5)
- **AND** infrastructure/schema changes SHALL be in phase 1
- **AND** cleanup-after changes SHALL be in the highest phase number

#### Scenario: Small spec with few changes
- **WHEN** the planner decomposes a spec with fewer than 4 changes
- **THEN** all changes SHALL be assigned phase 1 (single milestone)

#### Scenario: Milestones disabled
- **WHEN** `milestones.enabled` is false or not set in orchestration.yaml
- **THEN** the planner SHALL still assign phases (no prompt change needed) but the dispatcher SHALL ignore them

### Requirement: Phase state tracking in orchestration-state.json
The orchestration state SHALL track `current_phase` (integer) and a `phases` object keyed by phase number. Each phase entry SHALL have: `status` (pending/running/completed), `tag` (git tag name or null), `server_port` (integer or null), `server_pid` (integer or null), `completed_at` (ISO timestamp or null).

#### Scenario: State initialization from plan
- **WHEN** `init_state()` processes a plan with phase assignments
- **THEN** the state SHALL contain `current_phase: 1` and a `phases` object with one entry per unique phase number, all with status `pending`

#### Scenario: Phase transition to running
- **WHEN** the first change in a phase is dispatched
- **THEN** that phase's status SHALL transition from `pending` to `running`

#### Scenario: Phase transition to completed
- **WHEN** all changes in the current phase reach a terminal status (merged, failed, or skipped)
- **THEN** that phase's status SHALL transition from `running` to `completed`

### Requirement: Phase-gated dispatch
`dispatch_ready_changes()` SHALL only dispatch changes whose `phase` value is less than or equal to `current_phase`. When all changes in `current_phase` are terminal, the dispatcher SHALL increment `current_phase` and trigger the milestone checkpoint before dispatching the next phase.

#### Scenario: Dispatch respects phase boundary
- **WHEN** current_phase is 1 and there are pending changes in phase 1 and phase 2
- **THEN** only phase 1 changes SHALL be eligible for dispatch
- **AND** phase 2 changes SHALL remain pending regardless of dependency satisfaction

#### Scenario: Phase advancement
- **WHEN** all phase 1 changes are merged/failed/skipped
- **THEN** `current_phase` SHALL advance to 2
- **AND** the milestone checkpoint SHALL be triggered for phase 1
- **AND** phase 2 changes SHALL become eligible for dispatch on the next poll cycle

#### Scenario: Cross-phase dependencies
- **WHEN** a phase 2 change depends on a phase 1 change
- **THEN** the phase 2 change SHALL wait for both phase advancement AND dependency satisfaction

### Requirement: Phase override in orchestration.yaml
Users SHALL be able to override phase assignments via `milestones.phase_overrides` in orchestration.yaml. The override is a map of change-name to phase-number. Overrides SHALL be applied after plan initialization, replacing the planner-assigned phase.

#### Scenario: Override applied
- **WHEN** orchestration.yaml contains `milestones.phase_overrides: { "catalog": 3 }` and the planner assigned catalog to phase 2
- **THEN** catalog SHALL be in phase 3 after state initialization

#### Scenario: No overrides
- **WHEN** orchestration.yaml has no `milestones.phase_overrides`
- **THEN** planner-assigned phases SHALL be used as-is
