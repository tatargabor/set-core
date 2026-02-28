## Why

The orchestrator's merge path has five reliability gaps exposed during a 6-change live batch: (1) agent rebase always fails on trivial conflicts because the agent gets 2 iterations with `--done manual` but the rebase prompt doesn't tell it to mark itself done, (2) `retry_merge_queue` retries 5 times on the exact same conflict without detecting that nothing changed, (3) merge-blocked changes are counted as "complete" by auto-replan, triggering false "all changes done" cycles, (4) every retry attempt emits an ERROR-level log for the same conflict, flooding logs with 25+ duplicate error entries per batch, and (5) after merge, new dependencies from the merged branch are missing on main because no `pnpm install` (or equivalent) runs post-merge — causing build failures on the live project.

## What Changes

- **Fix agent rebase prompt**: Include explicit instructions to signal completion after resolving the merge conflict, so the 2-iteration `--done manual` loop actually works
- **Smart merge retry**: Detect when retry produces the same conflict fingerprint (same files, same content hash) as the previous attempt and stop early instead of retrying 5 times
- **Exclude merge-blocked from "all complete" check**: `merge-blocked` status should not count as "complete" in the auto-replan all-done detection
- **Suppress duplicate merge error logs**: Only emit ERROR on the first merge conflict per change; subsequent retries use WARN level
- **Post-merge dependency install**: After a successful merge, run `pnpm install` (or the project's package manager install command) to ensure new dependencies from the merged branch are available on main before subsequent builds

## Capabilities

### New Capabilities
- `merge-conflict-resolution`: Orchestrator merge path hardening — agent rebase reliability, smart retry dedup, correct completion detection, and log noise reduction

### Modified Capabilities

## Impact

- **Modified files**: `bin/wt-orchestrate` (merge_change, _try_merge, retry_merge_queue, monitor_loop all-done check)
- **No new dependencies**
- **No breaking changes**: All fixes are internal to the merge path
