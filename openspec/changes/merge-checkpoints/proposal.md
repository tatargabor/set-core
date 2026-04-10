# Merge Checkpoints

## Why

Multi-hour orchestrations (6-12 changes) are fragile: if change 5 breaks and merges bad code into main, the recovery path works but is slow and brittle — it reconstructs state by field-clearing rather than restoring a known-good snapshot. Progress files (coverage, review findings) are filtered via regex rather than restored from a save point. The recovery module must manually track every new state field, making it a maintenance liability.

We need reliable, automatic restore points after each successful merge so that rolling back is a snapshot-load, not a reconstruction.

## What Changes

- **Merge hook**: After a successful merge + archive, automatically save a checkpoint (manifest entry + progress file snapshots)
- **Recovery enhancement**: Restore progress files from checkpoint snapshot instead of fragile JSONL/JSON filtering
- **Checkpoint listing**: API endpoint + CLI support for listing available restore points
- **Web UI integration**: "Restore to checkpoint" button on the dashboard
- **Documentation**: Explain why checkpoints matter and how to use recovery

## Capabilities

### New Capabilities
- `merge-checkpoint-save` — automatic checkpoint creation after each successful merge
- `checkpoint-list` — list available restore points with metadata

### Modified Capabilities
- `state-recovery` — use checkpoint snapshots for progress file restoration (fallback to legacy filtering)

## Impact

- **`lib/set_orch/merger.py`**: Hook after `archive_change()` to save checkpoint metadata + progress snapshots
- **`lib/set_orch/recovery.py`**: Checkpoint-first progress restore with legacy fallback
- **`lib/set_orch/api/actions.py`**: New endpoints for list/restore
- **`web/src/`**: Checkpoint list UI + restore button
- **`set/orchestration/checkpoints/`**: New directory in consumer projects (auto-created)
- **Disk**: ~50-200KB per checkpoint (state metadata + progress file copies), negligible
