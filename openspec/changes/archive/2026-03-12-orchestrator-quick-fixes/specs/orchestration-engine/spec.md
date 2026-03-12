## MODIFIED Requirements

### Requirement: Change dispatch with dependency ordering
The orchestrator SHALL dispatch changes respecting the dependency graph and parallelism limits.

#### Scenario: Dependency-ordered dispatch
- **WHEN** pending changes exist
- **THEN** the orchestrator SHALL first cascade failed dependencies (marking pending changes as failed if any dependency has status `failed` or `merge-blocked`)
- **AND** then dispatch only changes whose `depends_on` entries all have status `merged` or `skipped`
- **AND** respect the `max_parallel` limit (concurrent running + dispatched)

#### Scenario: Failed dependency cascade before dispatch
- **WHEN** a change has status `pending`
- **AND** any of its `depends_on` entries has status `failed` or `merge-blocked`
- **THEN** the orchestrator SHALL mark the pending change as `failed` with failure_reason indicating which dependency failed
- **AND** this cascade SHALL happen BEFORE any dispatch attempt in each monitor loop iteration

#### Scenario: Worktree creation and Ralph launch
- **WHEN** a change is dispatched
- **THEN** the orchestrator SHALL create a worktree via `wt-new`, bootstrap it (env files + dependencies), create the OpenSpec change, pre-create proposal.md, and start a Ralph loop via `wt-loop start --max 30 --done openspec --label {name} --model {effective_model} --change {name}`
- **AND** the effective model SHALL be resolved via `resolve_change_model()` (see per-change-model spec)
- **AND** no per-change token budget SHALL be passed — the iteration limit (`--max 30`) provides the safety net instead

### MODIFIED Requirements

### Requirement: Monitor loop polling
The orchestrator monitor loop SHALL poll active changes every 15 seconds.

#### Scenario: Poll interval
- **WHEN** the monitor loop is running
- **THEN** it SHALL sleep for `POLL_INTERVAL` (15) seconds between poll cycles

#### Scenario: Active time tracking
- **WHEN** polling and at least one change is actively progressing (Ralph loop with recent loop-state.json mtime, OR change in `verifying` status)
- **THEN** the orchestrator SHALL increment `active_seconds` by `POLL_INTERVAL`
- **AND** NOT count time during token budget wait or when all changes are idle
