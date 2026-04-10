## MODIFIED Requirements

### Requirement: State reconstruction from events
The system SHALL provide `reconstruct_state_from_events(state_path, events_path)` that rebuilds the state file by replaying `STATE_CHANGE` and `TOKENS` events from the JSONL audit trail. It SHALL preserve plan-origin fields (scope, complexity, depends_on) from the existing state file and only update runtime fields.

**Additionally**, `_reset_progress_files()` SHALL prefer checkpoint-based restoration over filtering when a checkpoint exists for the target change.

#### Scenario: Replay status transitions
- **WHEN** the events file contains `STATE_CHANGE` events for change `add-auth` going `pending→running→done`
- **THEN** after reconstruction, `add-auth` has status `"done"`

#### Scenario: Replay token updates
- **WHEN** the events file contains `TOKENS` events with increasing totals for a change
- **THEN** the change's `tokens_used` field reflects the last recorded total

#### Scenario: Running changes become stalled
- **WHEN** reconstruction finds changes with status `"running"` (process crashed mid-execution)
- **THEN** those changes are set to `"stalled"` (no live process to back the running status)

#### Scenario: Derive orchestrator status
- **WHEN** all changes have terminal status after replay
- **THEN** the orchestrator status is set to `"done"`

#### Scenario: Derive orchestrator status — mixed
- **WHEN** some changes have non-terminal status after replay
- **THEN** the orchestrator status is set to `"stopped"`

#### Scenario: No events file
- **WHEN** the events JSONL file does not exist
- **THEN** reconstruction fails gracefully and returns `False`

#### Scenario: Emit reconstruction event
- **WHEN** reconstruction completes successfully
- **THEN** a `STATE_RECONSTRUCTED` event is emitted with event count and final status

#### Scenario: Progress restore from checkpoint
- **WHEN** recovery targets change `cart-system` and `checkpoints/orch-cart-system/` exists
- **THEN** progress files (coverage-merged.json, review-findings.jsonl) are copied from the checkpoint directory to their canonical locations, replacing the current files

#### Scenario: Progress restore fallback to filtering
- **WHEN** recovery targets change `old-change` and no checkpoint directory exists for it
- **THEN** the legacy filtering logic is used (remove rolled-back entries from coverage/findings)

#### Scenario: Checkpoint manifest preserved during recovery
- **WHEN** recovery performs `git reset --hard`
- **THEN** the checkpoints directory (manifest.jsonl + per-change snapshots) is saved to temp before reset and restored after, same pattern as archive dirs
