## 1. Shared cleanup helper (core foundation)

- [x] 1.1 Create `lib/set_orch/change_cleanup.py` with `CleanupResult` dataclass (`worktree_removed: bool`, `branch_removed: bool`, `warnings: list[str]`) [REQ: cleanup-returns-a-structured-result]
- [x] 1.2 Implement `cleanup_change_artifacts(change_name, project_path) -> CleanupResult` with idempotent worktree removal: try both `{project}-wt-{name}` and `{project}-{name}` paths, `git worktree remove --force` when registered, `rm -rf` fallback when unregistered, always run `git worktree prune` [REQ: shared-cleanup-helper-for-change-artifacts]
- [x] 1.3 Implement idempotent branch deletion: `git branch -D change/{name}` with non-zero-exit tolerance when branch is absent [REQ: shared-cleanup-helper-for-change-artifacts]
- [x] 1.4 Add structured logging: INFO for each successful removal (worktree path / branch name), WARN for unregistered-worktree rm-rf fallback, WARN for unexpected git failures, DEBUG for no-op paths [REQ: shared-cleanup-helper-for-change-artifacts]
- [x] 1.5 Add unit tests in `tests/unit/test_change_cleanup.py` covering: both present, only worktree, only branch, neither present, repeated-call idempotency, unregistered-worktree fallback, both naming conventions (with and without `-wt-` infix) [REQ: shared-cleanup-helper-for-change-artifacts]

## 2. Dispatcher discovery fix

- [x] 2.1 Rewrite `_find_existing_worktree` in `lib/set_orch/dispatcher.py:1109` to exact-match basenames against `{project_name}-{name}` and `{project_name}-wt-{name}` instead of substring `in line` [REQ: python-_find_existing_worktree-uses-exact-basename-match]
- [x] 2.2 Collect all candidate matches across both conventions and suffix variants, return highest-numbered suffix when multiple, log at DEBUG listing candidates [REQ: python-_find_existing_worktree-uses-exact-basename-match]
- [x] 2.3 Add unit tests in `tests/unit/test_dispatcher.py` verifying: no false-positive substring matches, ambiguity tie-breaking by suffix across both conventions [REQ: python-_find_existing_worktree-uses-exact-basename-match]

## 3. Bash discovery hardening

- [x] 3.1 Refactor `find_existing_worktree` in `bin/set-common.sh:338` to collect ALL matches across every pattern variant (including `{repo}-{change}-N` Python-convention suffixes, currently unmatched) into an array instead of returning on first hit [REQ: find_existing_worktree-resolves-ambiguity-deterministically]
- [x] 3.2 Extract suffix number from each candidate (treat unsuffixed as rank 0) and return the highest-ranked path; WARN via `warn()` helper listing all candidates and the selected one [REQ: find_existing_worktree-resolves-ambiguity-deterministically]
- [x] 3.3 Document the ambiguity-resolution policy in a comment block above the function (why highest-suffix wins, when WARN fires, both naming conventions accepted) [REQ: find_existing_worktree-resolves-ambiguity-deterministically]
- [x] 3.4 Add a bats test (or shell-based test) in `tests/` exercising: single match, two-level ambiguity (bash convention), Python-convention suffix match, mixed-convention ambiguity, three-level suffix, no match [REQ: find_existing_worktree-resolves-ambiguity-deterministically]

## 4. set-merge `--worktree` flag

- [x] 4.1 Parse `--worktree <path>` in `bin/set-merge` arg loop; store in `explicit_worktree` variable [REQ: set-merge-accepts-explicit-worktree-path]
- [x] 4.2 When `explicit_worktree` is non-empty: validate it is an existing directory, then verify it is registered in `git -C "$project_path" worktree list --porcelain` (scope the git call to the project path explicitly, not the caller's cwd); on failure exit non-zero with a clear error naming the bad path [REQ: set-merge-accepts-explicit-worktree-path]
- [x] 4.3 When `explicit_worktree` is set and valid: skip `find_existing_worktree` and use the explicit path as `wt_path` [REQ: set-merge-accepts-explicit-worktree-path]
- [x] 4.4 When `--worktree` is absent: preserve existing discovery behavior (call `find_existing_worktree`) unchanged [REQ: set-merge-accepts-explicit-worktree-path]
- [x] 4.5 Update `usage()` in `bin/set-merge` to document `--worktree <path>` with a one-line description [REQ: set-merge-help-documents-worktree]

## 5. Merger passes explicit path + circuit-breaker

- [x] 5.1 In `lib/set_orch/merger.py:merge_change` build the `set-merge` command conditionally: append `["--worktree", wt_path]` when `change.worktree_path` is non-empty and the dir exists; log WARN and omit the flag otherwise [REQ: merger-passes-authoritative-worktree-path-to-set-merge]
- [x] 5.2 Add merge-stall counter logic alongside existing `ff_retry_count` / `total_merge_attempts`: read `change.extras.get("merge_stall_attempts", 0)`, increment on FF-merge failure via `update_change_field`, reset to 0 on successful merge [REQ: persistent-merge-stall-circuit-breaker]
- [x] 5.3 Read threshold with safe chained `.get()`: `state.extras.get("directives", {}).get("merge_stall_threshold", 6)`; default 6 when missing, zero, or extras absent [REQ: persistent-merge-stall-circuit-breaker]
- [x] 5.4 When counter >= threshold: (a) emit ERROR log with change name, attempt count, last exit code, first 500 chars of stdout and stderr BEFORE escalation; (b) set `change.status = "failed:merge_stalled"`; (c) remove from `state.merge_queue`; (d) call `escalate_change_to_fix_iss(state_file=state_file, change_name=change_name, stop_gate="merge", escalation_reason="merge_stalled", event_bus=event_bus)` [REQ: persistent-merge-stall-circuit-breaker] [REQ: circuit-breaker-logs-before-escalation]
- [x] 5.5 Verify no changes are required to `escalate_change_to_fix_iss` itself — the function already produces source `circuit-breaker:{escalation_reason}` internally, which satisfies the `_retry_parent_after_resolved` prefix match [REQ: circuit-breaker-source-merge_stalled-integrates-with-existing-pipeline]
- [x] 5.6 Add unit tests covering: explicit-path passthrough, missing-path WARN fallback, counter increment/reset on success, threshold crossing triggers escalation with correct kwargs, directive override respected, default threshold when directive missing [REQ: merger-passes-authoritative-worktree-path-to-set-merge] [REQ: persistent-merge-stall-circuit-breaker]

## 6. Issue manager cleanup integration

- [x] 6.1 In `lib/set_orch/issues/manager.py:_retry_parent_after_resolved`, import `cleanup_change_artifacts` and call it for the parent change BEFORE `reset_change_to_pending` [REQ: parent-retry-cleans-artifacts-before-state-reset]
- [x] 6.2 Wrap the cleanup call in try/except; on failure, log WARN with parent name + exception and record `parent_retry_cleanup_degraded` audit entry, but still proceed to `reset_change_to_pending` [REQ: parent-retry-cleans-artifacts-before-state-reset]
- [x] 6.3 Update the successful-path `parent_retry_requested` audit entry to include the CleanupResult (worktree_removed / branch_removed / warnings) so operators can see what was removed [REQ: parent-retry-cleans-artifacts-before-state-reset]
- [x] 6.4 Add unit tests covering: cleanup runs before reset, cleanup failure does not block reset, audit log contains cleanup_result, merge_stalled escalation registers issue with correct source string [REQ: parent-retry-cleans-artifacts-before-state-reset] [REQ: circuit-breaker-source-merge_stalled-integrates-with-existing-pipeline]

## 7. Recovery helper alignment

- [x] 7.1 Update `reset_change_to_pending` in `lib/set_orch/recovery.py:464` to clear `merge_stall_attempts` from `ch.extras` as part of the gate-result extras reset [REQ: reset_change_to_pending-does-not-silently-leave-on-disk-artifacts]
- [x] 7.2 Update the docstring on `reset_change_to_pending` to explicitly state that the helper does NOT touch on-disk artifacts and that callers must use `cleanup_change_artifacts` (circuit-breaker path) or the plan-driven worktree/branch loops (recovery path) if they want a fresh re-dispatch [REQ: reset_change_to_pending-does-not-silently-leave-on-disk-artifacts]
- [x] 7.3 Do NOT refactor `set-recovery`'s existing inline `plan.worktrees_to_remove` / `plan.branches_to_delete` loops — they already handle idempotency (`if not os.path.isdir` skip; git non-zero exits logged) and work against the plan's possibly-archived-suffix paths which `cleanup_change_artifacts` would not cover [REQ: recovery-plan-execution-tolerates-already-removed-artifacts]
- [x] 7.4 Verify the recovery executor's "worktree dir already gone" / "branch delete skipped" log paths still fire correctly and update any related test mocks if signatures shift [REQ: recovery-plan-execution-tolerates-already-removed-artifacts]

## 8. Integration validation

- [x] 8.1 Add an integration test in `tests/unit/test_merge_collision_regression.py` that reproduces the failure mode: seed a change with `worktree_path=None`, pre-existing `change/foo` branch and `{project}-wt-foo` dir, then call `_retry_parent_after_resolved` and verify artifacts are gone and the next `_unique_worktree_name` returns `foo` (not `foo-2`) [REQ: parent-retry-cleans-artifacts-before-state-reset] [REQ: shared-cleanup-helper-for-change-artifacts]
- [x] 8.2 Add an integration test that seeds a stuck merge scenario (mock `set-merge` always returns non-zero), calls `merge_change` up to threshold+1 times, verifies status transitions to `failed:merge_stalled`, fix-iss is created, and an issue with source `circuit-breaker:merge_stalled` is registered [REQ: persistent-merge-stall-circuit-breaker] [REQ: circuit-breaker-source-merge_stalled-integrates-with-existing-pipeline]
- [x] 8.3 Manual verification: run the existing test suite in `tests/unit/` to ensure no regression in merger/recovery/issue tests [REQ: merger-passes-authoritative-worktree-path-to-set-merge]

## Acceptance Criteria (from spec scenarios)

### change-artifact-cleanup

- [x] AC-1: WHEN `cleanup_change_artifacts("foo", "/repos/acme")` runs AND the worktree is registered AND the branch exists THEN git worktree remove + prune + branch -D all run and each successful removal logs at INFO [REQ: shared-cleanup-helper-for-change-artifacts, scenario: worktree-and-branch-both-present]
- [x] AC-2: WHEN the worktree directory does not exist THEN git worktree remove is skipped, prune still runs, and the function does not raise [REQ: shared-cleanup-helper-for-change-artifacts, scenario: worktree-already-removed-on-disk]
- [x] AC-3: WHEN the worktree directory exists but is not registered THEN rm -rf fallback is used and a WARN is logged [REQ: shared-cleanup-helper-for-change-artifacts, scenario: worktree-exists-but-is-unregistered]
- [x] AC-4: WHEN the branch is already absent THEN `git branch -D` is skipped or its non-zero exit is ignored and the function does not raise [REQ: shared-cleanup-helper-for-change-artifacts, scenario: branch-already-deleted]
- [x] AC-5: WHEN the helper is called twice for the same change THEN the second call succeeds as a no-op [REQ: shared-cleanup-helper-for-change-artifacts, scenario: repeated-invocation-is-idempotent]
- [x] AC-6: WHEN a `{project}-{name}` (no `-wt-`) worktree exists THEN it is also considered for removal alongside `{project}-wt-{name}` [REQ: shared-cleanup-helper-for-change-artifacts, scenario: alternative-naming-conventions-recognised]
- [x] AC-7: WHEN cleanup completes THEN the return object has `worktree_removed`, `branch_removed`, `warnings` fields [REQ: cleanup-returns-a-structured-result, scenario: structured-return-value]
- [x] AC-8: WHEN the helper runs for a change with no artifacts THEN both booleans are False and warnings is empty [REQ: cleanup-returns-a-structured-result, scenario: all-absent-no-op]

### merger

- [x] AC-9: WHEN `merge_change` runs with `change.worktree_path` pointing to an existing directory THEN the set-merge subprocess receives `--worktree <path>` [REQ: merger-passes-authoritative-worktree-path-to-set-merge, scenario: worktree_path-is-known]
- [x] AC-10: WHEN `change.worktree_path` is empty or null THEN set-merge is called without `--worktree` and a WARN is logged [REQ: merger-passes-authoritative-worktree-path-to-set-merge, scenario: worktree_path-is-missing]
- [x] AC-11: WHEN `change.worktree_path` is set but the directory is missing THEN WARN is logged, `--worktree` is omitted, and set-merge's discovery fallback runs [REQ: merger-passes-authoritative-worktree-path-to-set-merge, scenario: worktree_path-points-to-a-missing-directory]
- [x] AC-12: WHEN `merge_change` ends with an FF failure THEN `merge_stall_attempts` is incremented and persisted [REQ: persistent-merge-stall-circuit-breaker, scenario: stall-counter-increments-on-every-ff-failure]
- [x] AC-13: WHEN merge succeeds THEN `merge_stall_attempts` is cleared [REQ: persistent-merge-stall-circuit-breaker, scenario: successful-merge-resets-the-stall-counter]
- [x] AC-14: WHEN `reset_change_to_pending` runs THEN `merge_stall_attempts` is cleared alongside other gate-result extras [REQ: persistent-merge-stall-circuit-breaker, scenario: state-reset-clears-the-stall-counter]
- [x] AC-15: WHEN the counter reaches threshold (default 6) THEN status becomes `failed:merge_stalled`, the change leaves the merge queue, and escalate_change_to_fix_iss is called with the correct kwargs (stop_gate="merge", escalation_reason="merge_stalled") [REQ: persistent-merge-stall-circuit-breaker, scenario: threshold-crossed-escalate-via-fix-iss]
- [x] AC-16: WHEN `state.extras["directives"]["merge_stall_threshold"]` is set to N THEN escalation fires at attempt N; WHEN absent THEN default 6 applies without KeyError [REQ: persistent-merge-stall-circuit-breaker, scenario: threshold-respects-directive-override]
- [x] AC-17: WHEN the circuit-breaker fires THEN an ERROR log entry precedes escalation with change name, attempt count, last exit code, stdout head, stderr head [REQ: circuit-breaker-logs-before-escalation, scenario: escalation-log-line]

### merge-worktree

- [x] AC-18: WHEN user runs `set-merge foo --worktree <path>` THEN the explicit path is used and `find_existing_worktree` is NOT called [REQ: set-merge-accepts-explicit-worktree-path, scenario: explicit-worktree-path-accepted]
- [x] AC-19: WHEN `--worktree <missing>` is given THEN the command exits non-zero with an error naming the bad path [REQ: set-merge-accepts-explicit-worktree-path, scenario: explicit-path-does-not-exist]
- [x] AC-20: WHEN `--worktree <path>` points at a non-worktree directory THEN the command exits non-zero with an error [REQ: set-merge-accepts-explicit-worktree-path, scenario: explicit-path-is-not-a-registered-git-worktree]
- [x] AC-21: WHEN user runs `set-merge foo` without `--worktree` THEN discovery via `find_existing_worktree` is used (existing behavior) [REQ: set-merge-accepts-explicit-worktree-path, scenario: no-worktree-flag-discovery-fallback]
- [x] AC-22: WHEN user runs `set-merge --help` THEN the output lists `--worktree <path>` with description [REQ: set-merge-help-documents-worktree, scenario: help-lists-the-flag]

### worktree-tools

- [x] AC-23: WHEN one worktree matches the change-id THEN `find_existing_worktree` returns it with no WARN [REQ: find_existing_worktree-resolves-ambiguity-deterministically, scenario: single-unambiguous-match]
- [x] AC-24: WHEN both `<project>-wt-<id>` and `<project>-wt-<id>-2` exist THEN `-2` is returned and a WARN lists all candidates [REQ: find_existing_worktree-resolves-ambiguity-deterministically, scenario: multiple-bash-convention-suffixes-highest-wins]
- [x] AC-25: WHEN both `<project>-<id>` and `<project>-<id>-2` (Python convention) exist THEN `-2` is returned with a WARN [REQ: find_existing_worktree-resolves-ambiguity-deterministically, scenario: multiple-python-convention-suffixes-highest-wins]
- [x] AC-26: WHEN both `<project>-wt-<id>` and `<project>-<id>` exist (cross-convention) THEN ambiguity is reported and a deterministic choice is made [REQ: find_existing_worktree-resolves-ambiguity-deterministically, scenario: mixed-convention-ambiguity]
- [x] AC-27: WHEN `-2` and `-3` both exist THEN `-3` is returned with a WARN [REQ: find_existing_worktree-resolves-ambiguity-deterministically, scenario: three-level-suffix-ranking]
- [x] AC-28: WHEN no worktree matches THEN the function echoes an empty string [REQ: find_existing_worktree-resolves-ambiguity-deterministically, scenario: no-matches]
- [x] AC-29: WHEN ambiguity is WARNed THEN the caller's exit status is still 0 [REQ: find_existing_worktree-resolves-ambiguity-deterministically, scenario: warning-is-idempotent-and-non-fatal]
- [x] AC-30: WHEN `_find_existing_worktree(project, "foo")` runs THEN it matches `{project}-foo` or `{project}-wt-foo` exactly and does NOT match `{project}-foobar` [REQ: python-_find_existing_worktree-uses-exact-basename-match, scenario: exact-match-against-both-conventions]
- [x] AC-31: WHEN multiple suffix variants match across both conventions THEN the highest suffix is returned with a DEBUG log of candidates [REQ: python-_find_existing_worktree-uses-exact-basename-match, scenario: suffix-variants-recognised-by-same-rule-as-bash-helper]

### issue-state-machine

- [x] AC-32: WHEN `_retry_parent_after_resolved` runs for a circuit-breaker issue with parent in `failed:*` THEN `cleanup_change_artifacts` runs BEFORE `reset_change_to_pending` [REQ: parent-retry-cleans-artifacts-before-state-reset, scenario: cleanup-precedes-state-reset]
- [x] AC-33: WHEN cleanup raises or returns warnings THEN WARN is logged, the audit entry `parent_retry_cleanup_degraded` is recorded, and `reset_change_to_pending` still runs [REQ: parent-retry-cleans-artifacts-before-state-reset, scenario: cleanup-failure-does-not-block-reset]
- [x] AC-34: WHEN cleanup + reset both succeed THEN the audit entry `parent_retry_requested` includes the cleanup_result [REQ: parent-retry-cleans-artifacts-before-state-reset, scenario: cleanup-emits-a-successful-audit-entry]
- [x] AC-35: WHEN the merger invokes `escalate_change_to_fix_iss(..., escalation_reason="merge_stalled", ...)` THEN a fix-iss dir is created, an issue is registered with source `circuit-breaker:merge_stalled` and affected_change set to the parent, and parent.fix_iss_child points at the new change [REQ: circuit-breaker-source-merge_stalled-integrates-with-existing-pipeline, scenario: merge_stalled-escalation-registers-an-issue]
- [x] AC-36: WHEN a `merge_stalled` fix-iss resolves THEN `_retry_parent_after_resolved` matches on the `circuit-breaker:` prefix and runs the same cleanup+reset sequence [REQ: circuit-breaker-source-merge_stalled-integrates-with-existing-pipeline, scenario: parent-auto-retry-on-merge_stalled-resolution]

### dispatch-recovery

- [x] AC-37: WHEN `IssueManager._retry_parent_after_resolved` resets a parent THEN `cleanup_change_artifacts` runs first and the removal is audit-logged [REQ: reset_change_to_pending-does-not-silently-leave-on-disk-artifacts, scenario: circuit-breaker-retry-pairs-cleanup-with-reset]
- [x] AC-38: WHEN `set-recovery` executes its plan THEN the existing inline worktree/branch removal loops continue to be used (not replaced by `cleanup_change_artifacts`) [REQ: reset_change_to_pending-does-not-silently-leave-on-disk-artifacts, scenario: recovery-cli-retains-its-plan-driven-worktree-branch-removal]
- [x] AC-39: WHEN a developer reads `reset_change_to_pending`'s docstring THEN it explicitly warns that FS artifacts are NOT removed and references `cleanup_change_artifacts` OR the recovery plan path [REQ: reset_change_to_pending-does-not-silently-leave-on-disk-artifacts, scenario: reset_change_to_pending-documents-the-contract]
- [x] AC-40: WHEN `reset_change_to_pending(ch)` runs THEN `ch.extras["merge_stall_attempts"]` is cleared alongside other gate-result extras [REQ: reset_change_to_pending-does-not-silently-leave-on-disk-artifacts, scenario: reset_change_to_pending-clears-the-merge-stall-counter]
- [x] AC-41: WHEN the recovery executor encounters a worktree already gone THEN it logs at INFO and continues without failing [REQ: recovery-plan-execution-tolerates-already-removed-artifacts, scenario: worktree-already-removed]
- [x] AC-42: WHEN the recovery executor encounters a branch already gone THEN it logs at INFO and continues without raising [REQ: recovery-plan-execution-tolerates-already-removed-artifacts, scenario: branch-already-deleted]
