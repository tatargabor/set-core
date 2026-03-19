## MODIFIED Requirements

### Requirement: Change dispatch with process verification
The orchestration engine SHALL use `set-orch-core process check-pid` instead of raw `kill -0` when verifying Ralph process liveness during dispatch, resume, and redispatch operations. The dispatch flow SHALL call `set-orch-core process safe-kill` instead of manual `kill -TERM; sleep; kill -KILL` sequences.

#### Scenario: Dispatch reads terminal PID and verifies identity
- **WHEN** dispatcher.sh reads `terminal_pid` from `loop-state.json` and stores it as `ralph_pid`
- **THEN** subsequent liveness checks use `set-orch-core process check-pid --pid $ralph_pid --expect-cmd "wt-loop"` instead of `kill -0 $ralph_pid`

#### Scenario: Redispatch kills with identity verification
- **WHEN** `redispatch_change()` needs to terminate a stuck Ralph process
- **THEN** it calls `set-orch-core process safe-kill --pid $ralph_pid --expect-cmd "wt-loop"` which verifies identity before each signal

#### Scenario: Orphan recovery uses process scanning
- **WHEN** `recover_orphaned_changes()` scans for orphaned processes
- **THEN** it calls `set-orch-core process find-orphans` instead of iterating PIDs with `kill -0`

### Requirement: State initialization via Python
The orchestration engine SHALL use `set-orch-core state init` to create the initial `orchestration-state.json` from the plan file, replacing the 40-line jq filter in `state.sh:init_state()`.

#### Scenario: init_state delegates to Python
- **WHEN** `init_state()` in state.sh is called with a plan file
- **THEN** it calls `set-orch-core state init --plan-file "$plan_file" --output "$STATE_FILENAME"` and verifies exit code 0

### Requirement: Proposal generation via Python templates
The orchestration engine SHALL use `set-orch-core template proposal` to generate `proposal.md` instead of the 3 concatenated heredocs in dispatcher.sh (PROPOSAL_EOF, MEMORY_EOF, SPECREF_EOF).

#### Scenario: Dispatch generates proposal via template
- **WHEN** `dispatch_change()` creates the proposal for a new change
- **THEN** it calls `set-orch-core template proposal` with the change name, scope, roadmap item, memory context, and spec reference, writing stdout to the proposal file
