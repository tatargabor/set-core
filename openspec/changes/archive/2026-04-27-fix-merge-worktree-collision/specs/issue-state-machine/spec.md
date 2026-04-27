## ADDED Requirements

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
