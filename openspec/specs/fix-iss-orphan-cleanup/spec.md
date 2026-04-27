# fix-iss-orphan-cleanup Specification

## Purpose
TBD - created by archiving change fix-iss-lifecycle-hardening. Update Purpose after archive.
## Requirements
### Requirement: Purge helper removes orphan fix-iss child artifacts

The issue manager SHALL provide a helper `_purge_fix_iss_child(issue, state_file, project_path, *, reason)` that removes the fix-iss child linked to an issue's `change_name` field. The helper SHALL be safe-by-default: it only touches artifacts when the child is provably not being worked on.

#### Scenario: Pending fix-iss with dir on disk — purged
- **WHEN** `_purge_fix_iss_child` runs for an issue whose `change_name` points at `fix-iss-007-foo`
- **AND** the state.changes entry for `fix-iss-007-foo` has status `pending`
- **AND** `openspec/changes/fix-iss-007-foo/` exists on disk
- **THEN** the state entry SHALL be removed
- **AND** the openspec directory SHALL be removed via `shutil.rmtree`
- **AND** an INFO log SHALL record the purge with reason, parent name, and fix-iss name

#### Scenario: Fix-iss already merged — skip
- **WHEN** the linked fix-iss child's status is `merged`
- **THEN** the helper SHALL NOT remove anything
- **AND** SHALL log at DEBUG that the child is merged (no orphan)

#### Scenario: Fix-iss is actively dispatched — skip with WARN
- **WHEN** the linked fix-iss child's status is one of `dispatched`, `running`, `verifying`, `integrating`
- **THEN** the helper SHALL NOT remove anything
- **AND** SHALL log at WARN that an active dispatch is in progress
- **AND** SHALL return without error so the caller can continue

#### Scenario: State entry present, dir already gone
- **WHEN** the state entry exists (status `pending` or `stopped`) but the openspec dir is absent
- **THEN** the state entry SHALL be removed
- **AND** the dir removal SHALL be skipped silently
- **AND** the INFO log SHALL note the dir-already-absent condition

#### Scenario: Dir present, no state entry
- **WHEN** the openspec dir exists but there is no state.changes entry
- **THEN** the dir SHALL be removed
- **AND** the INFO log SHALL note the state-already-absent condition

#### Scenario: Neither state nor dir — full no-op
- **WHEN** neither a state entry nor an openspec dir exists
- **THEN** the helper SHALL return without performing any removal
- **AND** log at DEBUG

#### Scenario: `issue.change_name` is missing or not a fix-iss
- **WHEN** `issue.change_name` is empty, or does not start with `fix-iss-`
- **THEN** the helper SHALL return immediately without side effects
- **AND** log at DEBUG that the issue does not reference a fix-iss child

### Requirement: Native-merge auto-resolve triggers orphan cleanup

When `_check_affected_change_merged` detects the parent change has been merged by the orchestrator and transitions the issue to RESOLVED, it SHALL immediately invoke `_purge_fix_iss_child(issue, state_file, project_path, reason="parent_merged")` so the linked fix-iss child does not linger as a stale pending entry.

#### Scenario: Parent merged, fix-iss child purged on auto-resolve
- **WHEN** an issue's `affected_change` has status `merged` in state
- **AND** the issue has a `change_name` pointing at a `pending` fix-iss child
- **THEN** `_check_affected_change_merged` SHALL transition the issue to RESOLVED
- **AND** SHALL invoke `_purge_fix_iss_child` with reason `parent_merged`
- **AND** the child's state entry SHALL be removed
- **AND** the child's openspec directory SHALL be removed

#### Scenario: Parent merged, no fix-iss child linked
- **WHEN** an issue's affected parent is merged
- **AND** `issue.change_name` is empty
- **THEN** auto-resolve SHALL transition to RESOLVED
- **AND** `_purge_fix_iss_child` SHALL be a no-op (no artifacts to clean)

#### Scenario: Purge failure does not block state transition
- **WHEN** `_purge_fix_iss_child` raises an unexpected exception (e.g. filesystem permission error)
- **THEN** the exception SHALL be caught, logged at WARN with the issue id and parent name
- **AND** the RESOLVED transition SHALL still succeed (cleanup is best-effort, not critical-path)

### Requirement: Escalation idempotency via `fix_iss_child` link

`escalate_change_to_fix_iss` SHALL check whether the parent already has a `fix_iss_child` field pointing at a live escalation before claiming a new `fix-iss-NNN-<slug>` directory. Re-escalation for a parent whose child is still active SHALL return the existing child name without creating a duplicate.

#### Scenario: Re-escalation with live prior child — return existing
- **WHEN** `escalate_change_to_fix_iss` is called for parent `P` with `escalation_reason="merge_stalled"`
- **AND** `P.fix_iss_child` is set to `fix-iss-003-foo`
- **AND** state.changes has an entry named `fix-iss-003-foo` with status in {`pending`, `dispatched`, `running`, `verifying`, `integrating`, `done`}
- **AND** `openspec/changes/fix-iss-003-foo/` exists on disk
- **THEN** the function SHALL return `fix-iss-003-foo` without writing a new proposal
- **AND** SHALL log at INFO that the parent already has a live escalation
- **AND** SHALL NOT register a new issue in the registry
- **AND** SHALL NOT emit a `FIX_ISS_ESCALATED` event

#### Scenario: Re-escalation with stale link — clear and proceed
- **WHEN** `P.fix_iss_child` is set but the state entry is missing OR the dir is missing OR the state status is a terminal-failure (`integration-failed`, `merge-failed`)
- **THEN** the function SHALL log at WARN listing which component is missing
- **AND** SHALL clear the stale `parent.fix_iss_child` field in state
- **AND** SHALL proceed with a fresh `_claim_fix_iss_dir` call
- **AND** SHALL register a new issue and emit the event as for a first-time escalation

#### Scenario: First-time escalation unaffected
- **WHEN** `P.fix_iss_child` is empty or null
- **THEN** the function SHALL behave as before (claim a fresh dir, register issue, emit event)
- **AND** SHALL set `P.fix_iss_child` to the new child name after successful claim

### Requirement: CLI command for orphan cleanup

The `set-orch-core` CLI SHALL provide an `issues cleanup-orphans` subcommand that scans a project for orphan fix-iss artifacts and removes them after operator confirmation.

#### Scenario: Dry-run lists orphans without modification
- **WHEN** user runs `set-orch-core issues cleanup-orphans --project myproj --dry-run`
- **THEN** the CLI SHALL list every orphan found: fix-iss name, parent name, parent status, issue state, state-entry status, dir presence
- **AND** SHALL NOT modify any state or filesystem
- **AND** SHALL exit 0 regardless of how many orphans are listed

#### Scenario: Interactive cleanup requires confirmation
- **WHEN** user runs the command without `--yes`
- **AND** at least one orphan is found
- **THEN** the CLI SHALL print the list and prompt `Remove N orphan(s)? [y/N]`
- **AND** on `y` SHALL invoke `_purge_fix_iss_child` for each
- **AND** on anything else SHALL exit without modification

#### Scenario: Non-interactive cleanup with --yes
- **WHEN** user runs the command with `--yes`
- **THEN** the CLI SHALL skip the prompt and purge every orphan found
- **AND** SHALL print the result (N purged, M skipped due to active dispatch, etc.)

#### Scenario: Orphan detection criteria
- **WHEN** the CLI scans the project
- **THEN** an entry SHALL be flagged as orphan if any of:
  - Parent change status is `merged` AND linked fix-iss child state entry exists with non-terminal status
  - Issue state is RESOLVED/DISMISSED/MUTED/CANCELLED AND linked fix-iss child state entry exists with non-terminal status
  - openspec fix-iss directory exists with NO corresponding state.changes entry AND NO active (non-terminal) issue in the registry

#### Scenario: No orphans found
- **WHEN** the CLI scans and finds zero orphans
- **THEN** it SHALL print an informational message and exit 0 without prompting

