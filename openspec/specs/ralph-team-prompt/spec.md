## ADDED Requirements

### Requirement: Team prompt injection
The Ralph engine prompt builder SHALL inject Agent Teams usage instructions into the Claude prompt when team mode is enabled in loop-state.json. The instructions SHALL be appended after the existing task/openspec instructions block in `build_prompt()`.

#### Scenario: Team mode enabled
- **WHEN** loop-state.json has `"team_mode": true`
- **THEN** `build_prompt()` SHALL include the team instructions block in the returned prompt

#### Scenario: Team mode disabled (default)
- **WHEN** loop-state.json has `"team_mode": false` or field is absent
- **THEN** `build_prompt()` SHALL NOT include any team instructions, prompt is identical to current behavior

### Requirement: Parallelization guidance
The team instructions block SHALL teach Claude when to use Agent Teams and when not to. The prompt MUST include:
1. A threshold rule: only spawn teams for 3+ independent tasks that can run in parallel
2. Task decomposition guidance: how to split an `/opsx:apply` task list into parallel chunks
3. Anti-pattern warnings: do NOT use teams for sequential tasks, file-contention tasks, or when only 1-2 tasks remain

#### Scenario: Apply with 5 independent tasks
- **WHEN** Claude receives an apply prompt with 5 unchecked tasks that don't share files
- **THEN** the team instructions guide Claude to spawn a team with 2-3 teammates, each assigned a subset of tasks

#### Scenario: Apply with 2 tasks
- **WHEN** Claude receives an apply prompt with only 2 remaining tasks
- **THEN** the team instructions guide Claude to work sequentially (below team threshold)

#### Scenario: Tasks share files
- **WHEN** tasks modify the same files (e.g., both modify index.ts)
- **THEN** the team instructions warn against parallelizing those specific tasks to avoid conflicts

### Requirement: Teammate subagent type
The team instructions SHALL specify that teammates MUST be spawned using the `Agent` tool with `subagent_type: "general-purpose"` and `mode: "bypassPermissions"`. Teammates SHALL run in foreground (not background) to ensure the team lead waits for their results.

#### Scenario: Teammate spawn configuration
- **WHEN** Claude spawns a teammate for a task
- **THEN** the teammate is created via `Agent` tool with `subagent_type: "general-purpose"`, `mode: "bypassPermissions"`, and `team_name` set to the created team

### Requirement: Task tracking via TaskCreate/TaskUpdate
The team instructions SHALL instruct Claude to use TaskCreate for each parallelizable task and TaskUpdate to track completion. The team lead MUST wait for all teammates to complete before committing.

#### Scenario: Team task lifecycle
- **WHEN** Claude spawns a team for parallel work
- **THEN** it creates tasks via TaskCreate, assigns them to teammates via TaskUpdate, and marks them completed as teammates finish

### Requirement: Commit coordination
The team instructions SHALL specify that ONLY the team lead commits code changes. Teammates SHALL make file changes but NOT create git commits. The team lead collects all changes and creates a single coherent commit after all teammates finish.

#### Scenario: Post-team commit
- **WHEN** all teammate tasks are completed
- **THEN** the team lead reviews the combined changes, resolves any conflicts, and creates one commit
