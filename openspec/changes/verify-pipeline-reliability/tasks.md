# Tasks: verify-pipeline-reliability

## 1. Dead verify agent detection

- [x] 1.1 Add `_has_live_children(pid)` helper in `engine.py` — uses `pgrep -P <pid>` to check if a process has any child processes [REQ: poll-detects-dead-verify-agent]
- [x] 1.2 Add `VERIFY_TIMEOUT = 600` constant and `verifying_since` timestamp tracking — set timestamp when change enters "verifying", store in change extras [REQ: verifying-status-has-timeout-guard]
- [x] 1.3 Add verifying-specific check in `_poll_active_changes` — for changes with status "verifying": check if `ralph_pid` is dead OR has no children OR verify timeout exceeded, and mark as "stalled" with appropriate reason [REQ: poll-detects-dead-verify-agent]
- [x] 1.4 Ensure `_resume_stalled_safe` handles stalled-from-verifying changes — verify that the existing resume path correctly re-dispatches verify for changes that were stalled during verify [REQ: stalled-verify-changes-are-recoverable]

## 2. Review diff scoping

- [x] 2.1 Modify `_get_merge_base()` in `verifier.py` — replace the `origin/HEAD` → `main` → `master` → `HEAD~5` fallback chain with `git merge-base HEAD main` as primary strategy, falling back to `HEAD~10` only on failure [REQ: review-diff-uses-true-fork-point]
- [x] 2.2 Verify the merge-base fix handles worktree context — ensure `git merge-base` works correctly when run inside a worktree (not the primary repo), resolving against the correct main branch ref [REQ: review-diff-uses-true-fork-point]
- [x] 2.3 Add logging for merge-base resolution — log which merge-base strategy was used (merge-base vs fallback) so E2E monitoring can track regressions [REQ: review-diff-excludes-unchanged-files]

## 3. Removed worktree resilience

- [x] 3.1 Add worktree existence check in `_poll_active_changes` — before calling `poll_change()`, check `os.path.isdir(change.worktree_path)`. If missing, auto-transition to "merged" with warning log [REQ: poll-skips-missing-worktrees]
- [x] 3.2 Add worktree existence check in worktree sync operations — in `_sync_running_worktrees()` (or equivalent post-merge sync), skip missing worktrees with debug-level log instead of error [REQ: sync-skips-missing-worktrees]
- [x] 3.3 Verify the auto-transition doesn't interfere with normal worktree creation — ensure that changes in "dispatched" status (worktree being created) aren't falsely detected as "missing worktree" [REQ: poll-skips-missing-worktrees]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a change has orch status "verifying" and ralph_pid has no child Claude process THEN the monitor marks it "stalled" with reason "dead_verify_agent" [REQ: poll-detects-dead-verify-agent, scenario: terminal-wrapper-alive-but-claude-cli-dead]
- [x] AC-2: WHEN a change has orch status "verifying" and ralph_pid is dead THEN the monitor marks it "stalled" [REQ: poll-detects-dead-verify-agent, scenario: both-terminal-wrapper-and-claude-cli-dead]
- [x] AC-3: WHEN a change has been in "verifying" for longer than verify_timeout THEN the monitor marks it "stalled" with reason "verify_timeout" [REQ: verifying-status-has-timeout-guard, scenario: verify-timeout-exceeded]
- [x] AC-4: WHEN watchdog detects a stalled change that was previously "verifying" THEN the change is re-dispatched [REQ: stalled-verify-changes-are-recoverable, scenario: watchdog-resumes-stalled-verify]
- [x] AC-5: WHEN a worktree branch was created before scaffold files were added to main THEN the review diff does NOT include those scaffold files [REQ: review-diff-uses-true-fork-point, scenario: worktree-branched-before-scaffold-addition]
- [x] AC-6: WHEN git merge-base fails THEN the system falls back to HEAD~10 with a warning [REQ: review-diff-uses-true-fork-point, scenario: merge-base-resolution-failure]
- [x] AC-7: WHEN a change has status "running" and its worktree_path does not exist THEN the monitor sets status to "merged" [REQ: poll-skips-missing-worktrees, scenario: running-change-with-missing-worktree]
- [x] AC-8: WHEN post-merge sync target worktree is missing THEN sync skips it with debug log [REQ: sync-skips-missing-worktrees, scenario: post-merge-sync-target-removed]
