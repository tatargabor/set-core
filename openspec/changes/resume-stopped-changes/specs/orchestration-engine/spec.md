## MODIFIED Requirements

### Requirement: Orchestrator resume after interrupt
When the orchestrator resumes from a stopped state, it SHALL resume changes that were running at the time of interruption.

#### Scenario: Resume stopped changes on restart
- **WHEN** the orchestrator resumes (status was "stopped")
- **AND** there are changes with status "stopped" in state.json
- **THEN** for each stopped change:
  - If the worktree directory exists: call `resume_change()` to re-dispatch
  - If the worktree directory does NOT exist: set status to "pending" for fresh dispatch
- **AND** log each resumed change: "Resuming stopped change: {name}"
- **AND** this SHALL happen BEFORE `dispatch_ready_changes()` is called

#### Scenario: Stall count not incremented on restart resume
- **WHEN** a stopped change is resumed on orchestrator restart
- **THEN** the stall_count SHALL NOT be incremented (this is a normal restart, not a stall)
