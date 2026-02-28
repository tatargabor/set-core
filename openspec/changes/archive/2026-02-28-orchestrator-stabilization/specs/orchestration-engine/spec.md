## MODIFIED Requirements

### Requirement: Monitor loop completion detection
The monitor loop SHALL check if all changes are in a terminal state (done, merged, merge-blocked, or failed). WHEN all changes are terminal AND auto_replan is enabled, the orchestrator SHALL trigger auto-replan. WHEN `trigger_checkpoint("completion")` is called, the orchestrator SHALL break from the monitor loop after the checkpoint is approved, preventing double-checkpoint.

#### Scenario: Completion with auto_replan
- **WHEN** all changes reach terminal status and auto_replan is true
- **THEN** auto_replan_cycle SHALL be called

#### Scenario: Completion without auto_replan
- **WHEN** all changes reach terminal status and auto_replan is false
- **THEN** trigger_checkpoint("completion") SHALL be called and the monitor loop SHALL break immediately after

### Requirement: Auto-replan stdout handling
During auto-replan, cmd_plan output SHALL be redirected to the log file (both stdout and stderr) to prevent terminal output interleaving with monitor loop messages.

#### Scenario: Auto-replan runs silently
- **WHEN** auto_replan_cycle calls cmd_plan
- **THEN** both stdout and stderr SHALL be redirected to LOG_FILE (`&>>"$LOG_FILE"`)

### Requirement: openspec new change error handling
WHEN `dispatch_change()` calls `openspec new change`, errors SHALL be logged (not swallowed). The `2>/dev/null || true` pattern SHALL be replaced with proper error capture and logging.

#### Scenario: openspec command fails
- **WHEN** `openspec new change` fails (not installed, permission error, etc.)
- **THEN** the error SHALL be logged via log_error and the dispatch SHALL fail with a clear message

### Requirement: Indentation correctness in monitor loop
The `orch_gate_stats` call in the non-auto_replan completion branch SHALL be correctly indented to match its enclosing block.

#### Scenario: Code block alignment
- **WHEN** the monitor loop reaches the non-auto_replan completion path
- **THEN** `orch_gate_stats` and `log_info "Orchestration complete"` SHALL be at the same indentation level within the else block

## ADDED Requirements

### Requirement: Auto-replan system
The orchestrator SHALL support automatic replanning via the `auto_replan` directive (default: false). WHEN all changes complete and auto_replan is true, the orchestrator SHALL re-run cmd_plan to find new work. The replan cycle number SHALL be tracked in state as `replan_cycle`. Accumulated `prev_total_tokens` and `active_seconds` SHALL be preserved across reinits.

#### Scenario: Auto-replan finds new work
- **WHEN** auto_replan_cycle returns rc=0 with novel changes
- **THEN** new changes SHALL be dispatched and the monitor loop SHALL continue

#### Scenario: Auto-replan finds no new work
- **WHEN** auto_replan_cycle returns rc=1
- **THEN** status SHALL be set to "done" and the orchestrator SHALL exit

### Requirement: Time limit safety net
The orchestrator SHALL support a `--time-limit` flag (default: 5h, "none" to disable). Active time is tracked only when loops are making progress (not during stalls). WHEN the time limit is reached, the orchestrator SHALL stop dispatching new changes and wait for running loops to finish.

#### Scenario: Time limit reached
- **WHEN** active_seconds exceeds time_limit_secs
- **THEN** the orchestrator SHALL log a warning, stop dispatching, and wait for running loops

#### Scenario: Time limit disabled
- **WHEN** --time-limit is set to "none"
- **THEN** the orchestrator SHALL run indefinitely

### Requirement: Base build verification
WHEN a worktree build fails, the orchestrator SHALL check if the main branch itself builds (`check_base_build()`). If main also fails, the orchestrator SHALL attempt an LLM-based fix (`fix_base_build_with_llm()`) and sync the worktree after the fix (`sync_worktree_with_main()`).

#### Scenario: Main branch build broken
- **WHEN** worktree build fails AND main branch build also fails
- **THEN** the orchestrator SHALL attempt LLM fix on main, commit the fix, and sync the worktree

#### Scenario: Main branch builds fine
- **WHEN** worktree build fails AND main branch build passes
- **THEN** the build failure is attributed to the change code and normal retry proceeds

### Requirement: Stale loop-state detection
WHEN a change has status "running" but its `loop-state.json` file has not been modified for more than 5 minutes, the orchestrator SHALL treat this as a stall and auto-resume the change.

#### Scenario: Loop state file goes stale
- **WHEN** loop-state.json mtime is older than 5 minutes for a running change
- **THEN** the orchestrator SHALL increment stall_count and resume the change

### Requirement: Retroactive worktree bootstrap
WHEN `dispatch_change()` finds an existing worktree that was not bootstrapped (missing .env or node_modules), it SHALL call `bootstrap_worktree()` to copy env files and install dependencies.

#### Scenario: Existing worktree without bootstrap
- **WHEN** a worktree exists but has no .env files or node_modules
- **THEN** bootstrap_worktree SHALL copy env files and install dependencies

### Requirement: Base build cache
The orchestrator SHALL cache the main branch build result in `BASE_BUILD_STATUS`/`BASE_BUILD_OUTPUT` variables. WHEN a merge completes successfully, the cache SHALL be invalidated (cleared) to force a fresh build check.

#### Scenario: Cache invalidation after merge
- **WHEN** a change is successfully merged to main
- **THEN** BASE_BUILD_STATUS and BASE_BUILD_OUTPUT SHALL be set to empty strings

### Requirement: Flexible worktree path discovery
`dispatch_change()` SHALL use `find_existing_worktree()` to discover worktree paths that may not follow the default `<project>-wt-<changename>` naming convention.

#### Scenario: Non-standard worktree path
- **WHEN** a worktree exists at a path different from the default convention
- **THEN** find_existing_worktree SHALL locate it and return the correct path
