# Spec: Orchestrator Restart Reliability

## Requirements

### LOCK-001: Sentinel cleans orchestrator lock before start
The sentinel MUST remove `orchestrator.lock` before starting the orchestrator process on the resume-restart path. The sentinel is the single supervisor — any existing lock when it starts a new orchestrator is stale.

### LOCK-002: Lock file contains PID for liveness check
The engine MUST write its PID to `orchestrator.lock` after acquiring the flock. If flock fails and the lock file contains a dead PID, the engine SHOULD remove the stale lock and re-acquire with a warning.

### LOCK-003: verify_retry_count preserved across orphan recovery
`recover_orphaned_changes()` MUST NOT reset `verify_retry_count` when recovering changes. The counter tracks total retries across the change lifetime and is needed for accurate E2E reporting.

### MERGE-001: merge_change detailed failure logging
`merge_change()` MUST log the exact git command, exit code, stdout, and stderr when ff-only merge fails. Currently failures are silent, making diagnosis impossible.

### MERGE-002: Enhanced merge-base divergence logging
The existing merge-base ancestor check in `merge_change()` SHOULD log detailed divergence information (commit counts, branch tips) when the relationship prevents ff-only merge.

### WT-001: Stale worktree cleanup on resume restart
On sentinel resume-restart (status=stopped/running), worktrees with numeric suffixes (`-2`, `-3`) where the base change is merged or absent from state SHOULD be removed. Active changes (running/pending/verifying) MUST NOT be affected.
