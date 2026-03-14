## ADDED Requirements

### Requirement: Git tag on phase completion
When a phase completes, the orchestrator SHALL create a lightweight git tag named `milestone/phase-N` (where N is the phase number) on the current HEAD commit.

#### Scenario: Successful tag creation
- **WHEN** phase 1 completes (all changes terminal)
- **THEN** a git tag `milestone/phase-1` SHALL be created on HEAD
- **AND** the tag name SHALL be stored in `phases["1"].tag` in state

#### Scenario: Tag already exists
- **WHEN** a milestone tag for this phase already exists (e.g., from a previous run)
- **THEN** the tag SHALL be force-updated to current HEAD (`git tag -f`)

### Requirement: Milestone worktree creation
On phase completion, the orchestrator SHALL create a git worktree from the milestone tag at `.claude/milestones/phase-N/`. The worktree provides a frozen snapshot of the codebase at the phase boundary for human review.

#### Scenario: Worktree created
- **WHEN** phase 1 completes and milestone tag is created
- **THEN** a worktree SHALL be created at `.claude/milestones/phase-1/` from tag `milestone/phase-1`

#### Scenario: Maximum worktree limit
- **WHEN** a new milestone worktree would exceed `milestones.max_worktrees` (default: 3)
- **THEN** the oldest milestone worktree SHALL be removed before creating the new one
- **AND** its dev server process SHALL be killed if still running

### Requirement: Dev server start in milestone worktree
On milestone worktree creation, the orchestrator SHALL start the detected dev server command in the worktree with a unique port assigned via `PORT` environment variable. The server process PID SHALL be stored in state.

#### Scenario: Server started
- **WHEN** milestone worktree for phase 1 is created and dev server is detected
- **THEN** the dev server SHALL be started in the background in the worktree directory
- **AND** `PORT=<base_port + phase_number>` SHALL be passed as environment variable
- **AND** the PID SHALL be stored in `phases["1"].server_pid`
- **AND** the port SHALL be stored in `phases["1"].server_port`

#### Scenario: No dev server detected
- **WHEN** no dev server command is detected and none is configured
- **THEN** the milestone worktree SHALL still be created (for manual review)
- **AND** `server_pid` and `server_port` SHALL remain null
- **AND** a log message SHALL note that no dev server was detected

#### Scenario: Server start failure
- **WHEN** the dev server command fails to start (non-zero exit within 5 seconds)
- **THEN** the failure SHALL be logged as a warning
- **AND** the milestone checkpoint SHALL NOT be blocked (non-fatal)

### Requirement: Email notification on phase completion
On phase completion, the orchestrator SHALL send an email via `send_email()` containing: phase number, list of merged changes, token cost, dev server URL (if running), and a note that the orchestrator continues automatically.

#### Scenario: Email sent with server URL
- **WHEN** phase 1 completes and dev server is running on port 3101
- **THEN** email SHALL be sent with subject `[wt-tools] <project> — Phase 1 complete (3/3 changes)`
- **AND** body SHALL include `http://localhost:3101` as review URL
- **AND** body SHALL include "Orchestrator continues automatically. Stop with: wt-orchestrate stop"

#### Scenario: Email sent without server
- **WHEN** phase completes but no dev server is running
- **THEN** email SHALL be sent without a review URL
- **AND** body SHALL note "No dev server configured — review the code directly"

#### Scenario: Email not configured
- **WHEN** RESEND_API_KEY is not set
- **THEN** email SHALL be silently skipped (existing behavior)

### Requirement: Non-blocking continuation
After triggering the milestone checkpoint (tag + worktree + server + email), the orchestrator SHALL immediately advance `current_phase` and continue dispatching. The orchestrator SHALL NOT wait for human approval.

#### Scenario: Immediate continuation
- **WHEN** phase 1 milestone checkpoint completes
- **THEN** `current_phase` SHALL be incremented
- **AND** phase 2 changes SHALL be eligible for dispatch on the same poll cycle
- **AND** orchestrator status SHALL remain `running` (not `checkpoint`)

### Requirement: Cleanup on orchestration completion
When orchestration completes (status transitions to `done`), the orchestrator SHALL kill all milestone dev server processes and remove all milestone worktrees. Git tags SHALL be preserved.

#### Scenario: Cleanup on normal completion
- **WHEN** orchestration status becomes `done`
- **THEN** all processes stored in `phases[*].server_pid` SHALL be killed (SIGTERM)
- **AND** all worktrees at `.claude/milestones/phase-*` SHALL be removed
- **AND** git tags `milestone/phase-*` SHALL NOT be removed

#### Scenario: Cleanup on stop
- **WHEN** user runs `wt-orchestrate stop`
- **THEN** milestone servers and worktrees SHALL be cleaned up (same as completion)
