# orchestration-skip Specification

## Purpose
CLI command and state management for skipping changes during orchestration, enabling the pipeline to continue past problematic changes.

## Requirements

### Requirement: Skip CLI command
The orchestrator SHALL provide a `wt-orchestrate skip <name>` subcommand that transitions a change to "skipped" status.

#### Scenario: Skip a failed change
- **WHEN** `wt-orchestrate skip my-change` is invoked
- **AND** the change "my-change" exists in the state file with status "failed"
- **THEN** the change status SHALL be set to "skipped"
- **AND** `skipped_at` SHALL be set to the current ISO 8601 timestamp
- **AND** a success message SHALL be printed

#### Scenario: Skip with reason
- **WHEN** `wt-orchestrate skip my-change --reason "spec issues, will revisit"` is invoked
- **AND** the change exists with a skippable status
- **THEN** the change status SHALL be set to "skipped"
- **AND** `skip_reason` SHALL be stored on the change object
- **AND** `skipped_at` SHALL be set to the current ISO 8601 timestamp

#### Scenario: Skip a pending change
- **WHEN** `wt-orchestrate skip my-change` is invoked
- **AND** the change has status "pending"
- **THEN** the change status SHALL be set to "skipped"

#### Scenario: Skip a stalled change
- **WHEN** `wt-orchestrate skip my-change` is invoked
- **AND** the change has status "stalled"
- **THEN** the change status SHALL be set to "skipped"

#### Scenario: Refuse to skip a running change
- **WHEN** `wt-orchestrate skip my-change` is invoked
- **AND** the change has status "running" or "verifying"
- **THEN** the command SHALL print an error message instructing the operator to pause the change first
- **AND** the status SHALL NOT be changed

#### Scenario: Skip a non-existent change
- **WHEN** `wt-orchestrate skip nonexistent` is invoked
- **AND** no change with that name exists in the state file
- **THEN** the command SHALL print an error message and exit with non-zero code

### Requirement: Skippable statuses
The skip command SHALL accept changes in the following statuses: "failed", "pending", "stalled", "merge-blocked", "build-blocked", "verify-failed", "paused". It SHALL reject changes in "running", "verifying", "dispatched", "merged", "done", or "skipped" status.

#### Scenario: Already skipped change
- **WHEN** `wt-orchestrate skip my-change` is invoked
- **AND** the change already has status "skipped"
- **THEN** the command SHALL print a message that the change is already skipped
- **AND** exit with zero code (idempotent)

#### Scenario: Already merged change
- **WHEN** `wt-orchestrate skip my-change` is invoked
- **AND** the change has status "merged" or "done"
- **THEN** the command SHALL print an error that merged changes cannot be skipped
