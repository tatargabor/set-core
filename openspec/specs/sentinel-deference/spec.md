# sentinel-deference Specification

## Purpose
TBD - created by archiving change sentinel-defers-to-orchestrator. Update Purpose after archive.
## Requirements
### Requirement: Deference principle
The sentinel SHALL classify all orchestration events into two tiers before acting:
- **Tier 1 (Defer)**: Situations the orchestrator handles automatically — sentinel MUST NOT intervene
- **Tier 2 (Act)**: Situations requiring sentinel action — process crashes, hangs, non-periodic checkpoints, terminal states

The sentinel MUST default to Tier 1 (defer) when uncertain about classification.

#### Scenario: Merge-blocked change detected in state
- **WHEN** sentinel observes a change with status "merge-blocked" in orchestration-state.json
- **THEN** sentinel SHALL take no action — the orchestrator's retry_merge_queue with jq deep-merge handles merge conflicts automatically

#### Scenario: Verify/test failure detected in state
- **WHEN** sentinel observes a change with verify or test failures
- **THEN** sentinel SHALL take no action — the orchestrator's max_verify_retries and fix cycles handle this

#### Scenario: Individual change marked failed
- **WHEN** sentinel observes a change with status "failed" while other changes are still active
- **THEN** sentinel SHALL take no action — the orchestrator marks failed changes and continues with others

#### Scenario: Replan cycle in progress
- **WHEN** sentinel observes the orchestrator performing a replan cycle
- **THEN** sentinel SHALL take no action — replan is a built-in orchestrator mechanism

#### Scenario: Token hard limit checkpoint triggered
- **WHEN** the orchestrator triggers a token_hard_limit checkpoint
- **THEN** sentinel SHALL NOT auto-approve — this is a non-periodic checkpoint requiring user decision

### Requirement: Simplified crash restart
The sentinel SHALL use a simple restart strategy for process crashes without elaborate error classification. The sentinel SHALL NOT read logs or attempt to diagnose the specific error type. The orchestrator saves state before exit, so a restart resumes from the last known state.

#### Scenario: Orchestrator process exits unexpectedly
- **WHEN** the orchestrator process exits and state is not a terminal state (done/stopped/time_limit)
- **THEN** sentinel SHALL wait 30 seconds and restart the orchestrator without reading logs or diagnosing the error

#### Scenario: Rapid crash loop detection
- **WHEN** the orchestrator crashes 5 times within 5 minutes of each start
- **THEN** sentinel SHALL stop, read the last 50 lines of orchestration.log, and report the error to the user

#### Scenario: Normal process exit
- **WHEN** the orchestrator process exits and state is done, stopped, or time_limit
- **THEN** sentinel SHALL treat this as a normal exit and produce the completion report

### Requirement: No state modification
The sentinel SHALL NOT modify orchestration-state.json except for auto-approving periodic checkpoints. The sentinel SHALL NOT reset state from "running" to "stopped" before restart — the orchestrator handles stale state on resume.

#### Scenario: Stale running state before restart
- **WHEN** sentinel is about to restart the orchestrator and state shows "running"
- **THEN** sentinel SHALL restart without modifying the state — the orchestrator's cmd_start handles stale running state

#### Scenario: Periodic checkpoint auto-approve
- **WHEN** sentinel detects a checkpoint with reason "periodic"
- **THEN** sentinel SHALL write approved=true to the checkpoint entry — this is the only permitted state modification

### Requirement: Minimal running event handling
The sentinel SHALL handle EVENT:running with zero analysis. No log reading, no state interpretation, no token-consuming diagnosis. Brief status message and immediate next poll.

#### Scenario: Running event received
- **WHEN** sentinel receives EVENT:running from a poll
- **THEN** sentinel SHALL output a one-line status summary and immediately start the next background poll cycle

