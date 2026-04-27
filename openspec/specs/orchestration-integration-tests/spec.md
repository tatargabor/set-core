# Orchestration Integration Tests Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Integration test infrastructure
The test suite SHALL provide reusable helpers to set up mock git repos, stub external commands, and assert on orchestrator state.

#### Scenario: Mock git repo setup
- **WHEN** a test calls `setup_test_repo`
- **THEN** a temporary git repo SHALL be created with a main branch and initial commit
- **AND** the repo SHALL be configured with `user.name` and `user.email` for commits
- **AND** the function SHALL return the repo path

#### Scenario: Feature branch creation
- **WHEN** a test calls `create_feature_branch <name> <files...>`
- **THEN** a branch `change/<name>` SHALL be created from main
- **AND** the specified files SHALL be committed on that branch
- **AND** the working directory SHALL return to main

#### Scenario: Stub run_claude
- **WHEN** `stub_run_claude` is active
- **THEN** calls to `run_claude` SHALL return a configurable exit code
- **AND** optionally create specified files (simulating agent output)
- **AND** no real Claude API calls SHALL be made

#### Scenario: Stub smoke command
- **WHEN** a test sets `smoke_command` to a stub script
- **THEN** the stub SHALL return a configurable exit code (0=pass, 1=fail)
- **AND** produce configurable stdout/stderr output

#### Scenario: Test cleanup
- **WHEN** a test completes (pass or fail)
- **THEN** all temporary directories, repos, and state files SHALL be removed

### Requirement: Merge pipeline tests
The test suite SHALL verify merge_change() behavior across success and failure paths.

#### Scenario: Clean merge → post-merge pipeline
- **WHEN** `merge_change` is called for a change with a clean merge
- **THEN** the branch SHALL be merged to main
- **AND** post_merge_command SHALL execute
- **AND** build verification SHALL run
- **AND** smoke tests SHALL run (if configured)
- **AND** the change status SHALL be `merged` → `completed`

#### Scenario: Merge conflict → merge-blocked
- **WHEN** `merge_change` is called and git merge produces a conflict
- **THEN** the change status SHALL be set to `merge-blocked`
- **AND** the orchestrator SHALL NOT crash (v8 bug #5 regression test)
- **AND** a merge retry counter SHALL be incremented

#### Scenario: Already-merged branch detection
- **WHEN** `merge_change` is called for a branch that is already an ancestor of HEAD
- **THEN** the change status SHALL be set to `merged`
- **AND** no merge operation SHALL be attempted

### Requirement: Smoke pipeline tests
The test suite SHALL verify the smoke blocking gate pipeline.

#### Scenario: Smoke pass (blocking mode)
- **WHEN** `smoke_blocking` is `true`
- **AND** smoke command returns 0
- **THEN** change status SHALL be `completed`
- **AND** `smoke_result` SHALL be `"pass"`
- **AND** the merge lock SHALL be released

#### Scenario: Smoke fail → fix → pass
- **WHEN** smoke command returns non-zero
- **AND** the stub fix agent creates a commit that makes smoke pass
- **THEN** `smoke_result` SHALL be `"fixed"`
- **AND** `smoke_fix_attempts` SHALL be 1
- **AND** change status SHALL be `completed`

#### Scenario: Smoke fail → fix exhausted
- **WHEN** smoke command returns non-zero
- **AND** the fix agent fails `smoke_fix_max_retries` times
- **THEN** change status SHALL be `smoke_failed`
- **AND** a critical notification SHALL have been sent
- **AND** the merge lock SHALL be released

#### Scenario: Health check fail
- **WHEN** the health check URL returns non-200 or times out
- **THEN** change status SHALL be `smoke_blocked`
- **AND** smoke tests SHALL NOT run
- **AND** a critical notification SHALL have been sent

### Requirement: Dispatch and loop control tests
The test suite SHALL verify ff→apply chaining behavior.

#### Scenario: ff→apply chaining test
- **WHEN** an ff iteration creates tasks.md
- **AND** `detect_next_change_action` returns `apply:*`
- **THEN** the test SHALL verify that the apply prompt is built and invoked
- **AND** the iteration counter SHALL not have incremented

#### Scenario: Stall detection test
- **WHEN** N consecutive iterations produce no commits
- **THEN** loop status SHALL be `stalled`
- **AND** N SHALL equal the configured stall threshold

#### Scenario: Repeated commit message detection test
- **WHEN** the same commit message appears in N consecutive iterations
- **THEN** loop status SHALL be `stalled`

### Requirement: Test execution and reporting
The test suite SHALL be runnable standalone and produce clear pass/fail output.

#### Scenario: Run all integration tests
- **WHEN** `./tests/orchestrator/test-orchestrate-integration.sh` is executed
- **THEN** all tests SHALL run sequentially
- **AND** output SHALL show test name, PASS/FAIL, and final summary
- **AND** exit code SHALL be 0 if all pass, 1 if any fail

#### Scenario: No external dependencies
- **WHEN** integration tests run
- **THEN** no Claude API calls SHALL be made
- **AND** no network access SHALL be required
- **AND** only bash, git, jq, and curl (for health check stubs) SHALL be needed
