## ADDED Requirements

### Requirement: Milestone checkpoint pipeline
The system SHALL provide `run_milestone_checkpoint(phase, base_port, max_worktrees, state_file)` that creates a milestone for a completed phase: git tag, worktree, dev server, email, event.

#### Scenario: Full milestone pipeline
- **WHEN** all changes in a phase reach terminal status
- **THEN** the system SHALL create git tag `milestone/phase-N`, create a worktree at `.claude/milestones/phase-N`, install dependencies, start dev server on `base_port + phase`, send milestone email, and emit MILESTONE_COMPLETE event

#### Scenario: No dev server detected
- **WHEN** no dev server command is available for the project
- **THEN** the system SHALL skip server start but still create the tag, worktree, and send email

### Requirement: Milestone worktree limit enforcement
The system SHALL enforce a configurable maximum number of milestone worktrees by removing the oldest when the limit is reached.

#### Scenario: Worktree limit exceeded
- **WHEN** the number of existing milestone worktrees equals or exceeds max_worktrees
- **THEN** the system SHALL kill the dev server of the oldest milestone, remove the oldest worktree, and repeat until under the limit

### Requirement: Milestone email notification
The system SHALL send an HTML email with phase completion statistics when a milestone checkpoint completes.

#### Scenario: Email with server
- **WHEN** a milestone completes with a running dev server
- **THEN** the email SHALL include a link to `http://localhost:<port>`, change count, token usage, and per-change status table

#### Scenario: Email without server
- **WHEN** a milestone completes without a dev server
- **THEN** the email SHALL include change count, token usage, and per-change status table without a server link

### Requirement: Milestone cleanup
The system SHALL provide `cleanup_milestone_servers()` and `cleanup_milestone_worktrees()` to tear down all milestone resources at orchestration end.

#### Scenario: Cleanup servers
- **WHEN** orchestration completes
- **THEN** the system SHALL kill all milestone dev server PIDs and clear them from state

#### Scenario: Cleanup worktrees
- **WHEN** orchestration completes
- **THEN** the system SHALL remove all directories under `.claude/milestones/` via `git worktree remove`
