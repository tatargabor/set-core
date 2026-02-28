## ADDED Requirements

### Requirement: Plan generation
The system SHALL decompose a project brief into an ordered list of OpenSpec changes via a single Claude CLI invocation.

#### Scenario: Generate plan from brief
- **WHEN** the developer runs `wt-orchestrate plan`
- **AND** `openspec/project-brief.md` exists with a `## Next` section containing roadmap items
- **THEN** the system SHALL invoke `claude -p` with the brief, existing spec names, active changes, and top 5 memory results
- **AND** write the resulting change plan to `orchestration-plan.json`
- **AND** display a summary of proposed changes with names, scopes, dependencies, and complexity estimates

#### Scenario: Plan output format
- **WHEN** a plan is generated
- **THEN** `orchestration-plan.json` SHALL contain:
  - `plan_version`: integer, incrementing on each replan
  - `brief_hash`: SHA-256 hex digest of project-brief.md at plan time
  - `created_at`: ISO 8601 timestamp
  - `changes`: array of change objects, each with `name` (kebab-case), `scope` (string), `complexity` (S/M/L), `depends_on` (array of change names), `roadmap_item` (string matching a Next bullet)

#### Scenario: No brief found
- **WHEN** the developer runs `wt-orchestrate plan`
- **AND** `openspec/project-brief.md` does not exist
- **THEN** the system SHALL exit with error: "No project brief found. Create openspec/project-brief.md first."

#### Scenario: Empty Next section
- **WHEN** the brief exists but the `## Next` section is empty or absent
- **THEN** the system SHALL exit with error: "No roadmap items in ## Next section."

### Requirement: Plan approval
The system SHALL require explicit developer approval before executing a plan.

#### Scenario: Show plan for review
- **WHEN** the developer runs `wt-orchestrate plan --show`
- **THEN** the system SHALL display the current plan in human-readable format: change names, scopes, dependency graph (ASCII), and estimated complexity

#### Scenario: Start requires existing plan
- **WHEN** the developer runs `wt-orchestrate start`
- **AND** no `orchestration-plan.json` exists
- **THEN** the system SHALL exit with error: "No plan found. Run 'wt-orchestrate plan' first."

### Requirement: Change dispatch
The system SHALL dispatch changes to worktrees and start Ralph loops based on the dependency graph.

#### Scenario: Dispatch independent change
- **WHEN** a change has status "pending" and all its `depends_on` changes have status "merged"
- **AND** the number of currently active changes is below `max_parallel`
- **THEN** the system SHALL:
  1. Create a worktree via `wt-new <change-name>`
  2. Create the change directory via `openspec new change <name>` in the worktree
  3. Write `brief-context.md` into the change directory with the change scope from the plan
  4. Start Ralph via `wt-loop start --max 30 --done openspec`

#### Scenario: Respect max parallel limit
- **WHEN** there are N changes with status "running" or "dispatched"
- **AND** N equals the `max_parallel` directive
- **THEN** the system SHALL NOT dispatch additional changes until an active change completes

#### Scenario: Dispatch changes with no dependencies first
- **WHEN** the orchestrator starts
- **THEN** it SHALL dispatch changes with empty `depends_on` arrays before changes with dependencies

### Requirement: Progress monitoring
The system SHALL poll active worktrees for Ralph loop status.

#### Scenario: Monitor loop
- **WHEN** the orchestrator is running
- **THEN** it SHALL read `<worktree>/.claude/loop-state.json` for each active change every 30 seconds
- **AND** update `orchestration-state.json` with current iteration, token usage, and status

#### Scenario: Change completion detected
- **WHEN** a change's Ralph loop status transitions to "done"
- **THEN** the system SHALL run the configured `test_command` in the worktree
- **AND** if tests pass, transition the change to "done" status
- **AND** if tests fail, transition to "failed" and notify the developer

#### Scenario: Stall detected
- **WHEN** a change's Ralph loop status is "stalled" or "stuck"
- **THEN** the system SHALL send a desktop notification with the change name and stall reason
- **AND** update the change status in orchestration-state.json accordingly

### Requirement: Orchestration state tracking
The system SHALL persist all orchestration state to `orchestration-state.json`.

#### Scenario: State file location
- **WHEN** the orchestrator creates or updates state
- **THEN** it SHALL write to `orchestration-state.json` in the project root
- **AND** the file SHALL be listed in `.gitignore`

#### Scenario: State file schema
- **WHEN** the orchestrator writes state
- **THEN** the JSON SHALL include:
  - `plan_version`: integer
  - `brief_hash`: string
  - `status`: one of "planning", "running", "paused", "checkpoint", "done"
  - `created_at`: ISO 8601 timestamp
  - `changes`: array of change objects with `name`, `status` (pending/dispatched/running/paused/done/merged/stalled/failed), `worktree_path`, `ralph_pid`, `started_at`, `completed_at`, `tokens_used`, `test_result`
  - `checkpoints`: array of checkpoint events with `at`, `type`, `approved`

### Requirement: Scope context via pre-created proposal
The orchestrator SHALL pre-create proposal.md from the plan scope instead of writing a separate context file.

#### Scenario: Dispatch creates proposal
- **WHEN** the orchestrator dispatches a change to a worktree
- **THEN** it SHALL create `openspec/changes/<name>/proposal.md` using the `scope` field from the plan
- **AND** the proposal SHALL include a Why section (from the roadmap item) and a What Changes section (from the scope)
- **AND** the proposal SHALL be recognized by `openspec status` as a completed artifact

#### Scenario: Ralph ff skips existing proposal
- **WHEN** Ralph runs `/opsx:ff` in a worktree where proposal.md already exists
- **THEN** ff SHALL detect the proposal as done and only create remaining artifacts (design, specs, tasks)

### Requirement: Post-apply verify step
The orchestrator SHALL run verification after Ralph reports a change as done.

#### Scenario: Verify after apply completion
- **WHEN** Ralph loop status transitions to "done" for a change
- **THEN** the orchestrator SHALL invoke `claude -p "Run /opsx:verify <change-name>" --max-turns 5 --dangerously-skip-permissions` in the worktree
- **AND** if verify passes, transition the change to "done" status
- **AND** if verify finds issues, restart Ralph for one retry iteration

#### Scenario: Verify retry limit
- **WHEN** verify fails after one Ralph retry
- **THEN** the orchestrator SHALL mark the change as "failed"
- **AND** notify the developer

### Requirement: Orchestrator cleanup on exit
The orchestrator SHALL handle signals gracefully.

#### Scenario: SIGTERM/SIGINT handling
- **WHEN** the orchestrator process receives SIGTERM or SIGINT
- **THEN** it SHALL update orchestration-state.json status to "stopped"
- **AND** log the stop event to `.claude/orchestration.log`

#### Scenario: Optional pause on exit
- **WHEN** the orchestrator exits via signal
- **AND** the `pause_on_exit` directive is true
- **THEN** it SHALL send SIGTERM to all running Ralph loops
- **AND** update each running change status to "paused"

#### Scenario: Default behavior on exit
- **WHEN** the orchestrator exits via signal
- **AND** `pause_on_exit` is not set or false
- **THEN** Ralph loops SHALL continue running independently

### Requirement: Orchestrator logging
The orchestrator SHALL log all significant events.

#### Scenario: Log file location
- **WHEN** the orchestrator writes log entries
- **THEN** it SHALL append to `.claude/orchestration.log`
- **AND** each entry SHALL be prefixed with an ISO 8601 timestamp

#### Scenario: Log rotation
- **WHEN** the orchestrator starts
- **AND** `.claude/orchestration.log` exceeds 100KB
- **THEN** it SHALL truncate the file keeping the last 50KB

#### Scenario: Logged events
- **WHEN** a state transition, dispatch, merge, checkpoint, or error occurs
- **THEN** it SHALL be logged with event type and relevant details

### Requirement: Token budget
The orchestrator SHALL support a total token budget across all changes.

#### Scenario: Token budget exceeded
- **WHEN** the `token_budget` directive is set to a positive integer
- **AND** cumulative tokens across all changes exceed the budget
- **THEN** the orchestrator SHALL enter wait mode (skip dispatching new changes, wait for running loops to finish)
- **AND** log a warning with per-change token breakdown
- **NOTE**: The orchestrator enters wait mode, not checkpoint mode, on budget exceeded

#### Scenario: No token budget
- **WHEN** the `token_budget` directive is not set or is 0
- **THEN** the orchestrator SHALL NOT enforce any token limit

### Requirement: Auto-merge pipeline
The system SHALL merge completed changes according to the configured merge policy.

#### Scenario: Eager merge
- **WHEN** merge policy is "eager"
- **AND** a change transitions to "done" with passing tests
- **AND** a dry-run merge check detects no conflicts
- **THEN** the system SHALL immediately run `wt-merge <change-name> --no-push`
- **AND** run `wt-close <change-name>`
- **AND** transition the change status to "merged"

#### Scenario: Checkpoint merge
- **WHEN** merge policy is "checkpoint"
- **AND** a change transitions to "done" with passing tests
- **THEN** the system SHALL add the change to the merge queue
- **AND** execute all queued merges only when the developer runs `wt-orchestrate approve --merge`

#### Scenario: Manual merge
- **WHEN** merge policy is "manual"
- **THEN** the system SHALL NOT merge any changes automatically
- **AND** SHALL display pending merges in status output

#### Scenario: Merge conflict detection
- **WHEN** the system attempts to merge a change
- **AND** `git merge --no-commit --no-ff <branch>` followed by `git merge --abort` indicates conflicts
- **THEN** the system SHALL mark the change as "merge-blocked"
- **AND** notify the developer with the conflicting file list

#### Scenario: Dependency unlock after merge
- **WHEN** a change transitions to "merged"
- **THEN** the system SHALL check all pending changes
- **AND** dispatch any change whose `depends_on` are all in "merged" status

### Requirement: Pause and resume
The system SHALL support pausing and resuming individual changes or the entire plan.

#### Scenario: Pause single change
- **WHEN** the developer runs `wt-orchestrate pause <change-name>`
- **AND** the change is currently "running"
- **THEN** the system SHALL send SIGTERM to the Ralph terminal PID
- **AND** update the change status to "paused" in orchestration-state.json

#### Scenario: Pause all
- **WHEN** the developer runs `wt-orchestrate pause --all`
- **THEN** the system SHALL pause all changes with status "running"
- **AND** set the orchestration status to "paused"

#### Scenario: Resume single change
- **WHEN** the developer runs `wt-orchestrate resume <change-name>`
- **AND** the change has status "paused"
- **THEN** the system SHALL restart Ralph in the existing worktree: `cd <worktree> && wt-loop start --max 30 --done openspec`
- **AND** update the change status to "running"

#### Scenario: Resume all
- **WHEN** the developer runs `wt-orchestrate resume --all`
- **THEN** the system SHALL resume all paused changes (respecting max_parallel)

### Requirement: Replan
The system SHALL support re-planning from an updated brief while preserving completed work.

#### Scenario: Replan command
- **WHEN** the developer runs `wt-orchestrate replan`
- **THEN** the system SHALL:
  1. Read the current orchestration-state.json (completed/active/pending changes)
  2. Read the updated project-brief.md
  3. Call Claude with both, asking: "Given this state, what changes are needed?"
  4. Write an updated plan to orchestration-plan.json with incremented plan_version

#### Scenario: Preserve completed work
- **WHEN** a replan occurs
- **THEN** changes with status "merged" SHALL remain unchanged in the new plan
- **AND** changes with status "running" SHALL continue unless the replan explicitly removes them

#### Scenario: Brief staleness warning
- **WHEN** the orchestrator detects that `project-brief.md` has a different SHA-256 hash than `brief_hash` in the state
- **THEN** it SHALL display a warning: "Brief has changed since plan was created. Consider running 'wt-orchestrate replan'."

### Requirement: Auto-replan system
The orchestrator SHALL support automatic replanning via the `auto_replan` directive (default: false). When all changes complete and auto_replan is true, the orchestrator SHALL re-run cmd_plan to find new work.

#### Scenario: Auto-replan finds new work
- **WHEN** all changes reach terminal status and auto_replan is true
- **AND** auto_replan_cycle returns rc=0 with novel changes
- **THEN** new changes SHALL be dispatched and the monitor loop SHALL continue
- **AND** replan_cycle SHALL be incremented in state

#### Scenario: Auto-replan finds no new work
- **WHEN** auto_replan_cycle returns rc=1
- **THEN** status SHALL be set to "done" and the orchestrator SHALL exit

#### Scenario: Cumulative stats preserved across replans
- **WHEN** a replan reinitializes state
- **THEN** prev_total_tokens, active_seconds, started_epoch, and time_limit_secs SHALL be preserved

### Requirement: Time limit safety net
The orchestrator SHALL support a `--time-limit` flag (default: 5h, "none" to disable). Active time is tracked only when loops are making progress.

#### Scenario: Time limit reached
- **WHEN** active_seconds exceeds time_limit_secs
- **THEN** the orchestrator SHALL log a warning, stop dispatching, and wait for running loops

#### Scenario: Time limit disabled
- **WHEN** --time-limit is set to "none"
- **THEN** the orchestrator SHALL run indefinitely

#### Scenario: Duration parsing
- **WHEN** --time-limit is provided
- **THEN** parse_duration() SHALL accept formats like "5h", "30m", "2h30m", "7200"
- **AND** format_duration() SHALL render seconds back to human-readable form

### Requirement: Flexible worktree path discovery
dispatch_change() SHALL use find_existing_worktree() to discover worktree paths that may not follow the default `<project>-wt-<changename>` naming convention.

#### Scenario: Non-standard worktree path
- **WHEN** a worktree exists at a path different from the default convention
- **THEN** find_existing_worktree SHALL locate it via `git worktree list` and return the correct path

### Requirement: Auto-merge approach
The system SHALL merge completed changes using `wt-merge --llm-resolve` directly without a dry-run pre-check.

#### Scenario: Merge with conflict resolution
- **WHEN** the orchestrator merges a completed change
- **THEN** it SHALL call `wt-merge <change-name> --no-push --llm-resolve`
- **AND** LLM-based conflict resolution SHALL be attempted automatically

### Deferred

- **Self-test Level 2-4 fixtures**: Integration test scripts with fixture worktrees and mock states. Not yet implemented.
- **ASCII DAG dependency graph**: Visualization of change dependency graph in `--show` output. Not yet implemented.

### Requirement: Status display
The system SHALL provide a human-readable status overview.

#### Scenario: Status command
- **WHEN** the developer runs `wt-orchestrate status`
- **THEN** the system SHALL display:
  - Overall status (planning/running/paused/done)
  - Per-change: name, status, iteration progress (N/M), tokens used
  - Merge queue (changes waiting for merge)
  - Total token consumption
  - Brief staleness indicator (current/stale)
