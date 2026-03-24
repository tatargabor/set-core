# Issue State Machine

## ADDED Requirements

## IN SCOPE
- 13 states with validated transitions
- Deterministic tick-based processing (no LLM calls in tick)
- State-specific behavior per tick cycle
- Timeout countdown and auto-approval
- Retry with backoff for FAILED issues
- Concurrency limits (max parallel investigations, max 1 fix)
- User actions (investigate, fix, dismiss, cancel, skip, mute, extend timeout)

## OUT OF SCOPE
- Event-driven architecture (polling only)
- Distributed state (single-machine only)
- Custom state definitions (fixed 13 states)

### Requirement: Valid state transitions
The state machine SHALL enforce a strict transition table. Any attempt to transition to a state not listed as valid from the current state SHALL raise an error and be logged.

#### Scenario: Valid transition
- **WHEN** an issue in NEW state transitions to INVESTIGATING
- **THEN** the transition succeeds and is logged to the audit trail

#### Scenario: Invalid transition rejected
- **WHEN** code attempts to transition an issue from NEW directly to FIXING
- **THEN** the transition is rejected with an error (NEW cannot go to FIXING)

### Requirement: Tick-based processing
The state machine SHALL process all active issues every tick cycle (configurable, default 5s). Processing SHALL be deterministic — no LLM calls, only state checks and transitions. Issues belonging to a group SHALL be skipped (group drives their lifecycle).

#### Scenario: NEW issue auto-triaged
- **WHEN** tick processes an issue in NEW state that is not muted and auto_investigate is enabled
- **THEN** an investigation agent is spawned and the issue transitions to INVESTIGATING (if concurrency allows)

#### Scenario: NEW issue muted
- **WHEN** tick processes an issue in NEW state that matches a mute pattern
- **THEN** the issue transitions to MUTED

### Requirement: Investigation completion handling
The state machine SHALL monitor investigation agents. When an investigation completes, it SHALL collect the diagnosis, update the issue's severity from the diagnosis impact, and apply post-diagnosis policy routing.

#### Scenario: Successful investigation
- **WHEN** the investigation agent completes with a parseable diagnosis
- **THEN** the issue transitions to DIAGNOSED and policy routing determines next state

#### Scenario: Investigation timeout
- **WHEN** the investigation agent exceeds timeout_seconds
- **THEN** the agent is killed, the issue transitions to DIAGNOSED with no diagnosis, and a human must decide

### Requirement: Timeout-based auto-approval
The state machine SHALL support countdown-based auto-approval for AWAITING_APPROVAL issues. When the timeout_deadline passes, the issue SHALL automatically transition to FIXING.

#### Scenario: Timeout expires
- **WHEN** an issue in AWAITING_APPROVAL reaches its timeout_deadline
- **THEN** it transitions to FIXING and a fix agent is spawned

#### Scenario: User acts before timeout
- **WHEN** a user clicks "Fix Now" on an AWAITING_APPROVAL issue before timeout
- **THEN** the timeout is cancelled and the issue immediately transitions to FIXING

### Requirement: Fix concurrency limit
The state machine SHALL enforce max 1 fix running at a time. When a fix is requested but another is running, the request SHALL be queued and processed when the slot opens.

#### Scenario: Fix queued
- **WHEN** a fix is requested but another issue is already in FIXING state
- **THEN** the fix is logged as "queued" and retried next tick

### Requirement: Auto-retry on failure
The state machine SHALL auto-retry failed issues up to max_retries times with configurable backoff. After exhausting retries, the issue SHALL stay in FAILED for manual intervention.

#### Scenario: Auto-retry within budget
- **WHEN** a fix fails and retry_count < max_retries and backoff has elapsed
- **THEN** the issue transitions back to INVESTIGATING with retry_count incremented

#### Scenario: Retries exhausted
- **WHEN** a fix fails and retry_count >= max_retries
- **THEN** the issue stays in FAILED, requiring manual action

### Requirement: Cancel action
The state machine SHALL support cancelling in-progress investigations and fixes. Cancel SHALL kill the running agent and transition to CANCELLED state.

#### Scenario: Cancel investigation
- **WHEN** user cancels an issue in INVESTIGATING state
- **THEN** the investigation agent is killed and the issue transitions to CANCELLED

#### Scenario: Cancel fix
- **WHEN** user cancels an issue in FIXING state
- **THEN** the fix agent is killed and the issue transitions to CANCELLED
