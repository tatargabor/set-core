# Issue State Machine

## Purpose

Define the issue lifecycle as a 13-state machine with deterministic tick-based processing, validated transitions, timeout-based auto-approval, retry-with-backoff for failures, and bounded concurrency (max 1 fix in flight). Issues belonging to a group are driven by their group; standalone issues progress per the rules below.

### In scope
- 13 states with validated transitions
- Deterministic tick-based processing (no LLM calls in tick)
- State-specific behavior per tick cycle
- Timeout countdown and auto-approval
- Retry with backoff for FAILED issues
- Concurrency limits (max parallel investigations, max 1 fix)
- User actions (investigate, fix, dismiss, cancel, skip, mute, extend timeout)

### Out of scope
- Event-driven architecture (polling only)
- Distributed state (single-machine only)
- Custom state definitions (fixed 13 states)
## Requirements
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

### Requirement: Parent retry cleans artifacts before state reset

When the issue manager auto-retries a failed parent change (after a circuit-breaker fix-iss child resolves), it SHALL remove the parent's on-disk worktree directory and `change/<name>` branch BEFORE resetting the parent's in-memory state to `pending`.

#### Scenario: Cleanup precedes state reset
- **WHEN** `IssueManager._retry_parent_after_resolved(issue)` runs for a circuit-breaker issue whose parent is in `failed:*`
- **THEN** the manager SHALL call `cleanup_change_artifacts(parent_name, project_path)` first
- **AND** only afterwards SHALL `reset_change_to_pending(ch)` be called on the parent Change

#### Scenario: Cleanup failure does not block reset
- **WHEN** `cleanup_change_artifacts` raises or returns with warnings
- **THEN** the manager SHALL log the failure at WARN with the parent change name
- **AND** `reset_change_to_pending` SHALL still be called so the parent exits the `failed:*` terminal state
- **AND** the audit log SHALL record `parent_retry_cleanup_degraded` with the failure detail

#### Scenario: Cleanup emits a successful audit entry
- **WHEN** cleanup succeeds and state reset succeeds
- **THEN** the audit log SHALL record `parent_retry_requested` with the parent name, prior status, and a flag indicating artifacts were cleaned

### Requirement: Circuit-breaker source `merge_stalled` integrates with existing pipeline

The merger's merge-stall circuit-breaker SHALL produce an issue whose `source` equals `circuit-breaker:merge_stalled` by calling `escalate_change_to_fix_iss` with `escalation_reason="merge_stalled"`. The existing `_retry_parent_after_resolved` guard (`issue.source.startswith("circuit-breaker:")`) SHALL match this source without further whitelisting.

#### Scenario: merge_stalled escalation registers an issue
- **WHEN** the merger invokes `escalate_change_to_fix_iss(..., escalation_reason="merge_stalled", ...)`
- **THEN** a fix-iss change directory SHALL be created under `openspec/changes/`
- **AND** an issue SHALL be registered in the IssueRegistry with `source="circuit-breaker:merge_stalled"` and `affected_change=<parent_name>`
- **AND** the parent change's `fix_iss_child` field SHALL be set to the new fix-iss change name

#### Scenario: Parent auto-retry on merge_stalled resolution
- **WHEN** a fix-iss child whose parent was escalated via `merge_stalled` resolves successfully
- **THEN** `_retry_parent_after_resolved` SHALL match on the `circuit-breaker:` prefix and run the same cleanup + reset sequence as for `token_runaway` parents
- **AND** no additional source-string whitelisting SHALL be required in the issue manager or policy engine

### Requirement: Auto-resolve on parent merge cleans orphan fix-iss child

When the issue manager's tick-loop auto-resolves an issue because the affected parent change merged natively (path: `_check_affected_change_merged`), the cleanup SHALL extend beyond the state transition to also remove the orphan fix-iss child that was never needed.

#### Scenario: Native merge + orphan pending fix-iss child
- **WHEN** `_check_affected_change_merged` observes the parent's status is `merged` in state
- **AND** the issue has a linked fix-iss child (`issue.change_name` starts with `fix-iss-`)
- **AND** the child's state entry status is `pending` or `stopped`
- **THEN** the issue SHALL transition to RESOLVED
- **AND** `_purge_fix_iss_child` SHALL be invoked with reason `parent_merged`
- **AND** the child SHALL be removed from state.changes
- **AND** the child's openspec directory SHALL be removed
- **AND** the audit log SHALL record `auto_resolved_by_orchestrator` (as today) plus `fix_iss_orphan_purged`

#### Scenario: Native merge + active fix-iss child
- **WHEN** the child's state entry is `dispatched` or `running`
- **THEN** the issue SHALL transition to RESOLVED
- **AND** `_purge_fix_iss_child` SHALL NOT remove the active child
- **AND** a WARN log SHALL note the active dispatch and suggest manual cleanup via the CLI

### Requirement: Escalation is idempotent against live parent↔child link

`escalate_change_to_fix_iss` SHALL check `parent.fix_iss_child` before claiming a new fix-iss directory and SHALL return the existing child name if a valid prior link exists, preventing silent duplicate escalations.

#### Scenario: Parent already linked, prior child still live
- **WHEN** the parent change already has `fix_iss_child=<name>` set
- **AND** the state entry for `<name>` exists with a non-terminal, non-failed status
- **AND** `openspec/changes/<name>/` exists
- **THEN** the function SHALL return `<name>` without side effects (no proposal write, no registry entry, no event)
- **AND** SHALL log at INFO that the escalation is a no-op

#### Scenario: Parent linked but prior child gone — clear and re-escalate
- **WHEN** `parent.fix_iss_child` points at a name whose state entry OR dir is missing (partially orphaned)
- **THEN** the function SHALL clear the stale link (`parent.fix_iss_child = None`)
- **AND** proceed with a fresh claim as for a first-time escalation
- **AND** the WARN log SHALL note the inconsistency that was auto-repaired

#### Scenario: Parent linked but prior child is terminal-failed
- **WHEN** the prior child's state status is `integration-failed` or `merge-failed`
- **THEN** the prior child is considered exhausted and re-escalation SHALL proceed
- **AND** the new fix-iss SHALL be claimed with a fresh NNN
- **AND** the WARN log SHALL include the prior child's terminal status

### Requirement: CLI surfaces orphan inventory and supports dry-run cleanup

A `set-orch-core issues cleanup-orphans` CLI command SHALL enumerate orphan fix-iss artifacts across a project and support both dry-run inspection and confirmed removal.

#### Scenario: Dry-run enumeration
- **WHEN** the operator runs the command with `--dry-run`
- **THEN** the CLI SHALL print a report of every orphan candidate with parent name, parent status, issue state, and which artifacts (state entry / openspec dir) are present
- **AND** SHALL NOT alter state or filesystem
- **AND** SHALL exit 0 regardless of count

#### Scenario: Interactive confirmation
- **WHEN** the command runs without `--yes` and finds at least one orphan
- **THEN** the CLI SHALL prompt the operator before deleting
- **AND** SHALL only proceed on an affirmative response

#### Scenario: Batch cleanup with --yes
- **WHEN** the command runs with `--yes`
- **THEN** the CLI SHALL remove every orphan found (subject to the safe-remove predicate)
- **AND** SHALL print a summary: N purged, M skipped (active), total

#### Scenario: Zero orphans
- **WHEN** the scan finds no orphans
- **THEN** the CLI SHALL print an informational line and exit 0 without prompting

### Requirement: Tick loop includes DIAGNOSED-stall watchdog

`IssueManager.tick()` SHALL call `_check_diagnosed_stalls()` on every tick cycle, alongside the existing `_check_timeout_reminders()` pass.

#### Scenario: Tick sequence includes the watchdog
- **WHEN** `tick()` runs
- **THEN** the method SHALL call `_check_diagnosed_stalls()` at least once per invocation
- **AND** the call SHALL occur after the `_process(issue)` loop so freshly-transitioned issues are evaluated by the watchdog on the NEXT tick (not the same tick that transitioned them)

#### Scenario: Watchdog errors do not break tick
- **WHEN** `_check_diagnosed_stalls` raises an unexpected exception
- **THEN** the exception SHALL be caught and logged at WARN
- **AND** the remainder of the tick (including `_check_timeout_reminders`) SHALL still run

