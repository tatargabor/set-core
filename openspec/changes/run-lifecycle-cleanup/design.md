# Design: run-lifecycle-cleanup

## Architecture

### Run Archive Directory Structure

```
wt/orchestration/runs/
  2026-03-21T10-30-00/           # timestamp of archive
    state.json                    # orchestration-state.json snapshot
    events.jsonl                  # event log
    coverage.json                 # requirement coverage mapping
    review-findings.jsonl         # review results
    review-findings-summary.md    # review summary
    state-archive.jsonl           # replan archive (if exists)
    meta.json                     # run metadata (spec hash, duration, change count, result)
```

### Unified Cleanup Flow

```
archive_previous_run()
  │
  ├─ 1. Check if state file exists → if not, skip archive
  │
  ├─ 2. Create runs/<timestamp>/ dir
  │
  ├─ 3. Copy per-run artifacts to archive:
  │     state.json, events.jsonl, coverage.json,
  │     review-findings.*, state-archive.jsonl
  │
  ├─ 4. Write meta.json (spec_hash, status, change_count, started_at, archived_at)
  │
  ├─ 5. Clean per-run files:
  │     rm state, events, coverage (reset to empty), findings, lock
  │
  └─ 6. Preserve: digest/*.json (except coverage), config, specs, directives
```

### Integration Points

**Sentinel startup** (bin/set-sentinel):
- Before any startup logic, call `archive_previous_run()` if state file exists and status is terminal (done/stopped/failed)
- `reset_for_spec_switch()` calls `archive_previous_run()` first, then does its additional git cleanup
- Fresh start (no state file) — no archive needed, just clean ephemeral files

**`set-orchestrate reset`** (bin/set-orchestrate):
- `cmd_reset --full` calls `archive_previous_run()` before resetting
- `cmd_reset --partial` does NOT archive (just resets failed→pending within same run)

**Engine replan** (lib/set_orch/engine.py):
- `_archive_completed_to_jsonl()` stays as-is (within-run replan archive)
- No change needed — this is intra-run, not inter-run

### Coverage Reset Logic

Coverage must be reset when a NEW run starts, but NOT during replan within the same run.

- `archive_previous_run()` resets coverage.json to `{"coverage": {}, "uncovered": []}`
- The engine's `reconcile_coverage()` builds coverage during the run from live state
- Replan does NOT reset coverage — it accumulates across cycles within one run

### Meta.json Format

```json
{
  "spec_hash": "abc123",
  "spec_path": "docs/v1-spec.md",
  "status": "done",
  "change_count": 6,
  "merged_count": 5,
  "failed_count": 1,
  "started_at": "2026-03-21T08:00:00Z",
  "archived_at": "2026-03-21T10:30:00Z",
  "duration_seconds": 9000
}
```

### Function Location

`archive_previous_run()` is a bash function in `bin/set-sentinel` (alongside `reset_for_spec_switch()` and `clean_old_worktrees()`). This keeps all lifecycle management in one place.

The function is idempotent — calling it when there's nothing to archive is a no-op.
