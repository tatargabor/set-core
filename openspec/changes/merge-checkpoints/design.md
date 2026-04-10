# Design: Merge Checkpoints

## Context

The orchestrator runs multi-hour sessions with 6-12+ changes. When a late change breaks things and merges bad code, recovery (`set-recovery`) works but is brittle: it reconstructs state by clearing individual fields and filtering progress files via regex. Every new state field added to `Change` must be manually added to the recovery field-clearing list — a maintenance trap.

The existing `orch/{change_name}` git tags already mark merge points. The gap is not "where to restore to" (git tags solve that) but "how to restore progress files reliably."

## Goals / Non-Goals

**Goals:**
- Automatic checkpoint metadata + progress snapshots after each merge
- Snapshot-based progress file restoration in recovery (no more regex filtering)
- Queryable checkpoint list (API + CLI)
- Web UI "restore to checkpoint" action

**Non-Goals:**
- Full state.json snapshots (contains stale PIDs, worktree paths — same complexity as field-clearing)
- Manual checkpoint creation (auto-only, triggered by merge)
- Checkpoint pruning (add later if disk becomes a concern)
- Replacing the git-reset + state-field-clearing parts of recovery (those work fine)

## Decisions

### 1. Manifest JSONL + per-checkpoint progress dirs (not full state snapshots)

**Choice:** Append-only JSONL manifest for metadata, per-change directories for progress file copies.

**Why not full state.json snapshots?** The state at merge time contains in-flight changes (status=implementing, ralph_pid=48291) that are stale on restore. A snapshot would need the same field-clearing as current recovery — just shifting complexity, not removing it. Progress files (coverage, findings) are the only data that benefits from exact-copy restoration.

**Alternatives considered:**
- SQLite checkpoint DB — overkill for append-only sequential data
- Git notes — poor querying, not visible in directory listings
- State.json deep copy — stale ephemeral data problem (see above)

### 2. Hook after archive_change(), before _remove_from_merge_queue()

**Choice:** Insert `_save_merge_checkpoint()` at merger.py ~line 655, after archive commit lands but before the change leaves the merge queue.

**Why here?** At this point: git tag exists, tokens finalized, archive committed, worktree cleaned. The progress files reflect the cumulative state including this merge. If checkpoint save fails, it's a WARNING — merge still succeeds.

### 3. Checkpoint dir survives git reset (same pattern as archive dirs)

**Choice:** During recovery, save `set/orchestration/checkpoints/` to temp before `git reset --hard`, restore after.

**Why?** The checkpoints are committed to git (part of archive commit), so `git reset --hard` to an earlier commit would delete later checkpoints. But we want to keep them for the manifest history and potential future restores. Same pattern already proven for archive dirs in recovery.py.

### 4. Recovery prefers checkpoint snapshot, falls back to legacy filtering

**Choice:** `_reset_progress_files()` checks for checkpoint dir first. If found, copy files from snapshot. If not (old runs without checkpoints), use existing regex filtering.

**Why?** Backward compatible. Old orchestration runs that predate this feature still recover correctly via the legacy path.

## Risks / Trade-offs

- **[Risk] Checkpoint save fails mid-write** → Mitigation: atomic write pattern (write to temp, rename). Failure is non-fatal WARNING.
- **[Risk] Manifest JSONL grows unbounded** → Mitigation: negligible (~200 bytes/entry, 100 changes = 20KB). Can add rotation later.
- **[Risk] Progress file copies add disk usage** → Mitigation: ~50-200KB per checkpoint. 30 checkpoints = ~6MB. Negligible.
- **[Trade-off] Not snapshotting state.json** → Simpler but means field-clearing in recovery.py still needs maintenance. Acceptable because the field-clearing is for a different concern (resetting change status) that snapshot wouldn't solve cleanly anyway.

## Open Questions

None — scope is well-defined from the exploration session.
