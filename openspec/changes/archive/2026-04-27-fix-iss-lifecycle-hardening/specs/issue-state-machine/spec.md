## ADDED Requirements

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
