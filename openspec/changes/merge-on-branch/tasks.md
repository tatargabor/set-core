# Tasks: merge-on-branch

## 1. CLI: Add --ff-only mode to set-merge

- [x] 1.1 Add `--ff-only` flag parsing to `bin/set-merge` argument handling [REQ: cli-ff-only-mode]
- [x] 1.2 Implement ff-only merge path: skip LLM resolution, conservation checks, and conflict handling; use `git merge --ff-only` directly [REQ: cli-ff-only-mode]
- [x] 1.3 On ff-only failure, exit with non-zero code and do NOT fall back to regular merge [REQ: cli-ff-only-mode]

## 2. State: Add new status values

- [x] 2.1 Add "integrating" and "integration-failed" to valid change status values in state.py [REQ: integration-status-tracking]
- [x] 2.2 Ensure monitor loop treats "integration-failed" as a terminal status (no re-polling, no dispatch) [REQ: integration-status-tracking]

## 3. Verifier: Integrate main before gates

- [x] 3.1 Add `_integrate_main_into_branch(wt_path, change_name, state_file)` helper to verifier.py that merges main into the branch worktree [REQ: integrate-main-before-gates]
- [x] 3.2 Add integration step at the start of `handle_change_done()`, after uncommitted work check and before gate pipeline construction [REQ: integrate-main-before-gates]
- [x] 3.3 Set change status to "integrating" during the integration merge [REQ: integration-status-tracking]
- [x] 3.4 If integration merge has no new commits (branch already up-to-date), skip and proceed to gates [REQ: integrate-main-before-gates]
- [x] 3.5 If integration merge conflicts, dispatch agent with retry_context explaining the conflict, set status back to "running" [REQ: integrate-main-before-gates]
- [x] 3.6 On re-entry after conflict resolution (agent done again), re-attempt integration before gates [REQ: integrate-main-before-gates]
- [x] 3.7 Add integration retry counter; after max retries (default 3), mark change as "integration-failed" [REQ: integrate-main-before-gates]

## 4. Merger: Switch to ff-only merge

- [x] 4.1 Change `merge_change()` to call `set-merge <change> --no-push --ff-only` instead of `--llm-resolve` [REQ: fast-forward-only-merge-to-main]
- [x] 4.2 Add `_fast_forward_main(change_name, state_file)` helper that handles the ff-only call and return code interpretation [REQ: fast-forward-only-merge-to-main]
- [x] 4.3 On ff-only failure: re-integrate main into branch (git merge main in worktree), set change status to "running", call `resume_change()` to re-trigger gate pipeline [REQ: fast-forward-only-merge-to-main]
- [x] 4.4 Add `ff_retry_count` field tracking and maximum retry limit (default 3, configurable via directives) [REQ: fast-forward-only-merge-to-main]
- [x] 4.5 On ff retry limit reached, mark change as "merge-blocked" [REQ: fast-forward-only-merge-to-main]

## 5. Merger: Remove post-merge build recovery

- [x] 5.1 Remove `_post_merge_build_check()` call from `merge_change()` success path [REQ: remove-post-merge-build-recovery]
- [x] 5.2 Remove `build_broken_on_main` flag set/clear from `merge_change()` [REQ: remove-post-merge-build-recovery]
- [x] 5.3 Remove `smoke_fix_scoped` import and call from `_blocking_smoke_pipeline()` [REQ: remove-post-merge-build-recovery]
- [x] 5.4 Keep all other post-merge steps: deps install, custom command, i18n sidecar, scope verify, archive, worktree sync [REQ: preserve-post-merge-non-build-steps]

## 6. Engine: Remove build_broken_on_main machinery

- [x] 6.1 Remove dispatch guard in `_dispatch_ready_safe()` that checks `build_broken_on_main` flag [REQ: remove-post-merge-build-recovery]
- [x] 6.2 Remove `_retry_broken_main_build_safe()` function and its periodic call in the monitor loop [REQ: remove-post-merge-build-recovery]
- [x] 6.3 Remove the periodic poll (every 5th cycle) that calls `_retry_broken_main_build_safe` [REQ: remove-post-merge-build-recovery]

## 7. Merger: Simplify conflict handling

- [x] 7.1 Remove or simplify `_handle_merge_conflict()` since conflicts are now resolved on branch, not during merge-to-main [REQ: fast-forward-only-merge-to-main]
- [x] 7.2 Remove agent-assisted rebase logic from merger.py (agent rebase now happens in verifier integration phase) [REQ: fast-forward-only-merge-to-main]
- [x] 7.3 Keep `_try_merge()` and `retry_merge_queue()` but update them to use ff-only path [REQ: fast-forward-only-merge-to-main]

## 8. Tests

- [x] 8.1 Add unit test for `_integrate_main_into_branch()`: clean merge, no-op when up-to-date, conflict detection [REQ: integrate-main-before-gates]
- [x] 8.2 Add unit test for ff-only merge path in merger.py: success case, failure-triggers-reintegration case [REQ: fast-forward-only-merge-to-main]
- [x] 8.3 Update E2E test stubs (set-merge mock in test harness) to support --ff-only flag [REQ: cli-ff-only-mode]
- [x] 8.4 Verify existing tests still pass with build_broken_on_main removal [REQ: remove-post-merge-build-recovery]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a change signals done and main has diverged THEN the system merges main into the branch and proceeds to gates [REQ: integrate-main-before-gates, scenario: successful-integration-with-no-conflicts]
- [x] AC-2: WHEN a change signals done and main has not advanced THEN the system skips integration and proceeds to gates [REQ: integrate-main-before-gates, scenario: integration-with-no-new-commits-on-main]
- [x] AC-3: WHEN integration produces conflicts THEN the agent is dispatched to resolve on branch [REQ: integrate-main-before-gates, scenario: integration-merge-conflict]
- [x] AC-4: WHEN conflict resolution succeeds THEN the system re-attempts integration and proceeds to gates [REQ: integrate-main-before-gates, scenario: conflict-resolution-succeeds]
- [x] AC-5: WHEN conflict resolution exhausts retries THEN status becomes "integration-failed" [REQ: integrate-main-before-gates, scenario: conflict-resolution-exhausts-retries]
- [x] AC-6: WHEN all gates pass and main has not advanced THEN ff-only merge succeeds and change is marked merged [REQ: fast-forward-only-merge-to-main, scenario: gates-pass-and-ff-only-succeeds]
- [x] AC-7: WHEN ff-only fails because main advanced THEN the system re-integrates and re-runs gates [REQ: fast-forward-only-merge-to-main, scenario: ff-only-fails-because-main-advanced]
- [x] AC-8: WHEN ff-only retry limit reached THEN change is marked merge-blocked [REQ: fast-forward-only-merge-to-main, scenario: ff-only-retry-limit-reached]
- [x] AC-9: WHEN set-merge --ff-only is called and branch is descendant THEN merge completes via fast-forward [REQ: cli-ff-only-mode, scenario: set-merge-with-ff-only-succeeds]
- [x] AC-10: WHEN set-merge --ff-only fails THEN exit non-zero without fallback [REQ: cli-ff-only-mode, scenario: set-merge-with-ff-only-fails]
- [x] AC-11: WHEN a change is merged via ff-only THEN no build check runs on main and build_broken_on_main is not set [REQ: remove-post-merge-build-recovery, scenario: no-build-check-after-merge]
- [x] AC-12: WHEN a change is merged via ff-only THEN deps install, custom command, i18n sidecar, scope verify, archive, and sync still run [REQ: preserve-post-merge-non-build-steps, scenario: post-merge-deps-and-archive-still-run]
