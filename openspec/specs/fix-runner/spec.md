# Fix Runner

## ADDED Requirements

## IN SCOPE
- Spawn claude CLI as fix agent in set-core directory with opsx workflow
- Max 1 fix at a time (hard limit)
- Fix agent runs /opsx:ff → /opsx:apply → /opsx:verify → /opsx:archive
- Fix completion detection and result collection
- Deploy via `set-project init` to target environments
- Kill/cancel support for running fixes

## OUT OF SCOPE
- Parallel fixes (always sequential)
- Worktree-based fixes (always set-core dir)
- Custom fix workflows (always opsx)
- Rollback on failed deploy

### Requirement: Fix agent spawning
The fix runner SHALL spawn a claude CLI process in the set-core directory with a prompt that instructs the agent to run the full opsx workflow for the issue's change name.

#### Scenario: Spawn fix agent
- **WHEN** the state machine triggers a fix for ISS-001 with diagnosis available
- **THEN** a claude CLI is spawned in set-core dir with prompt containing the diagnosis and opsx instructions

#### Scenario: Change name generation
- **WHEN** a fix is spawned for ISS-001 with error_summary "auth token crash"
- **THEN** the change name is generated as "fix-iss-001-auth-token-crash" (slugified, max 50 chars)

### Requirement: Sequential fix execution
The fix runner SHALL enforce max 1 fix at a time. Additional fix requests SHALL be queued and processed when the current fix completes.

#### Scenario: Only one fix runs
- **WHEN** ISS-001 is FIXING and ISS-002 requests a fix
- **THEN** ISS-002's fix is logged as "queued" and starts after ISS-001 completes

### Requirement: Fix completion detection
The fix runner SHALL detect when the fix agent process exits. It SHALL check whether the opsx change was successfully archived (presence of archive marker in the change directory).

#### Scenario: Successful fix
- **WHEN** the fix agent exits and the opsx change is archived
- **THEN** the issue transitions to VERIFYING

#### Scenario: Failed fix
- **WHEN** the fix agent exits without archiving the change
- **THEN** the issue transitions to FAILED

### Requirement: Deploy to environments
After verification passes, the fix runner SHALL deploy the fix by running `set-project init` on the source environment. Optionally, it SHALL deploy to all registered projects if configured.

#### Scenario: Deploy to source environment
- **WHEN** a fix is verified and deployment begins
- **THEN** `set-project init` is run on the project that reported the issue

#### Scenario: Deploy to all projects
- **WHEN** deploy_to_all is enabled in config
- **THEN** `set-project init` is run on all registered projects

### Requirement: Fix cancellation
The fix runner SHALL support killing a running fix agent. The associated opsx change SHALL be left in its current state (not cleaned up automatically).

#### Scenario: Cancel running fix
- **WHEN** user cancels a fix in FIXING state
- **THEN** the fix agent process is killed and the issue transitions to CANCELLED
