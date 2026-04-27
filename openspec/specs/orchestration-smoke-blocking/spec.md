# Orchestration Smoke Blocking Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## MODIFIED Requirements

### Requirement: Scoped smoke fix agent
When smoke tests fail, the fix agent SHALL receive change-specific context.

#### Scenario: Scoped fix prompt
- **WHEN** smoke tests fail for change `{name}`
- **THEN** the fix prompt SHALL include:
  - Smoke command and full output (not truncated to 2000 chars)
  - List of files modified by this change (`git diff HEAD~1 --name-only`)
  - Change scope description from state.json
  - Constraint: "MAY ONLY modify files that were part of this change"
  - Constraint: "MUST NOT delete or weaken existing test assertions"

#### Scenario: Multi-change fix context after checkpoint
- **WHEN** smoke tests fail after a checkpoint merge (multiple changes merged)
- **THEN** the fix prompt SHALL additionally include:
  - The list of ALL change names merged since the last successful smoke pass
  - A `git log --oneline {last_smoke_pass_commit}..HEAD` summary
  - Instruction: "Multiple changes were merged since the last smoke pass. The failure may be caused by an interaction between changes, not just the last one."

#### Scenario: Fix attempt verification
- **WHEN** the fix agent produces a commit
- **THEN** the orchestrator SHALL run unit tests + build before re-running smoke
- **AND** if unit tests or build fail, `git revert HEAD --no-edit` and count as failed attempt

#### Scenario: Fix succeeds
- **WHEN** the fix agent's changes cause smoke to pass
- **THEN** `smoke_result` SHALL be set to `"fixed"`
- **AND** `smoke_status` SHALL be set to `"done"`
- **AND** a Learning memory SHALL be saved

#### Scenario: Fix retries exhausted
- **WHEN** the fix agent fails `smoke_fix_max_retries` times (default: 3)
- **THEN** the change status SHALL be set to `smoke_failed`
- **AND** `smoke_status` SHALL be set to `"failed"`
- **AND** a critical notification SHALL be sent
- **AND** the merge lock SHALL be released

### Requirement: Granular smoke status tracking
State.json SHALL track smoke progress at a granular level.

#### Scenario: Status fields
- **WHEN** a change enters the post-merge smoke pipeline
- **THEN** state.json SHALL include per-change fields:
  - `smoke_status`: "pending" → "checking" → "running" → "fixing" → "done" | "failed" | "blocked" | "skipped"
  - `smoke_fix_attempts`: number of fix attempts made
  - `smoke_screenshot_dir`: path to collected screenshot artifacts (empty string if none)
  - `smoke_screenshot_count`: number of `.png` files collected (0 if none)

#### Scenario: Sentinel observability
- **WHEN** a change is in `smoking` state for more than 15 minutes
- **THEN** the sentinel poll SHALL be able to detect this via state.json timestamps

## Requirements

### Requirement: Last successful smoke tracking
The orchestrator SHALL track the commit SHA of the last successful smoke pass for multi-change regression context.

#### Scenario: Recording successful smoke
- **WHEN** a smoke test passes (result = "pass" or "fixed")
- **THEN** the orchestrator SHALL record `last_smoke_pass_commit` in state.json with the current `git rev-parse HEAD`

#### Scenario: Initial state
- **WHEN** orchestration starts and no `last_smoke_pass_commit` exists
- **THEN** the value SHALL default to empty string `""`
- **AND** multi-change context SHALL be unavailable until the first smoke pass establishes a baseline
- **NOTE**: NOT initialized to HEAD — this prevents false multi-change blame when main starts broken
