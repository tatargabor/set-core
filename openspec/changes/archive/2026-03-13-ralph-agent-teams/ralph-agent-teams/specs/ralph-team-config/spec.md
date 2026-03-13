## ADDED Requirements

### Requirement: Team mode CLI flag
`wt-loop start` SHALL accept a `--team` flag that enables Agent Teams mode for the loop. The flag SHALL default to off (disabled).

#### Scenario: Start with team mode
- **WHEN** user runs `wt-loop start "task" --team`
- **THEN** loop-state.json SHALL contain `"team_mode": true`

#### Scenario: Start without team flag
- **WHEN** user runs `wt-loop start "task"` (no --team flag)
- **THEN** loop-state.json SHALL contain `"team_mode": false`

### Requirement: Team mode in loop-state.json
The loop state initialization SHALL include a `team_mode` boolean field. The engine SHALL read this field at the start of each iteration to determine whether to include team instructions in the prompt.

#### Scenario: State persistence across iterations
- **WHEN** team_mode is set to true at start
- **THEN** it SHALL remain true across all iterations of the loop without re-reading CLI args

### Requirement: Team metrics in iteration state
Each iteration record in loop-state.json SHALL include team-related metrics when team mode is active: `team_spawned` (boolean), `teammates_count` (number), `team_tasks_parallel` (number of tasks run in parallel).

#### Scenario: Iteration with team usage
- **WHEN** an iteration uses Agent Teams
- **THEN** the iteration record includes `"team_spawned": true, "teammates_count": 2, "team_tasks_parallel": 4`

#### Scenario: Iteration without team usage
- **WHEN** team mode is enabled but Claude decides not to use teams (e.g., only 1 task)
- **THEN** the iteration record includes `"team_spawned": false, "teammates_count": 0, "team_tasks_parallel": 0`

### Requirement: Usage banner display
The Ralph loop startup banner SHALL display team mode status alongside existing mode/model/budget info.

#### Scenario: Banner with team mode
- **WHEN** team_mode is true
- **THEN** the startup banner line includes `Team: enabled` next to existing fields
