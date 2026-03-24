# Tasks

## 1. Merge Retry Counter Fix (merger.py + engine.py)

- [x] 1.1 Unify `MAX_MERGE_RETRIES` — remove the local `MAX_MERGE_RETRIES = 3` in `retry_merge_queue()` and use the global constant (set to 3) [REQ: merge-retry-limit-enforcement]
- [x] 1.2 In `execute_merge_queue()`, add retry counter CHECK (not increment) at the top of the loop: if `merge_retry_count >= MAX_MERGE_RETRIES`, set status to `integration-failed`, emit event, and skip [REQ: merge-retry-limit-enforcement]
- [x] 1.3 In `_poll_suspended_changes()`, check `merge_retry_count` before re-adding orphaned "done" changes to merge queue — if >= MAX, set `integration-failed` instead [REQ: merge-retry-limit-enforcement]
- [x] 1.4 Emit `CHANGE_INTEGRATION_FAILED` event when retry limit is reached (in both execute_merge_queue and _poll_suspended_changes) [REQ: merge-retry-limit-enforcement]

## 2. Stalled Change Recovery (engine.py)

- [x] 2.1 In `_poll_suspended_changes()`, add "stalled" to the status filter list [REQ: stalled-changes-with-completed-work-are-recovered]
- [x] 2.2 After the existing "done" handling block, add stalled handling: read loop-state.json, if status="done" → set change to "done" and add to merge queue [REQ: stalled-changes-with-completed-work-are-recovered]
- [x] 2.3 If loop-state is NOT "done", leave the change stalled (no automatic recovery for genuine stalls) [REQ: stalled-changes-with-completed-work-are-recovered]

## 3. Set-Merge FF-Only Fix (bin/set-merge)

- [x] 3.1 Remove `2>/dev/null` from `git merge --ff-only "$source_branch"` to expose error messages [REQ: diagnostic-output-on-ff-only-failure]
- [x] 3.2 Before ff-only merge, verify source branch exists with `git show-ref --verify "refs/heads/$source_branch"` — if not found, log error with branch name [REQ: ff-only-merge-resolves-worktree-branch-correctly]
- [x] 3.3 On ff-only failure, log diagnostic info: merge-base, HEAD, source branch HEAD, and the actual git error message [REQ: diagnostic-output-on-ff-only-failure]

## 4. Web Template Gitignore (modules/web)

- [x] 4.1 Create `.gitignore` in `modules/web/set_project_web/templates/nextjs/` with comprehensive entries (node_modules, .next, playwright-report, test-results, coverage, *.db, .env, tsconfig.tsbuildinfo, .claude/logs) [REQ: web-template-includes-comprehensive-gitignore]
- [x] 4.2 Add `.gitignore` to `modules/web/set_project_web/templates/nextjs/manifest.yaml` in the core file list [REQ: web-template-includes-comprehensive-gitignore]
- [x] 4.3 Verify `set-project init --project-type web --template nextjs` deploys the .gitignore correctly [REQ: template-gitignore-deployed-by-set-project-init]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN `execute_merge_queue()` processes a change with `merge_retry_count >= 3` THEN it sets status to `integration-failed` and does NOT call `merge_change()` [REQ: merge-retry-limit-enforcement, scenario: change-exceeds-retry-limit-in-execute-merge-queue]
- [x] AC-2: WHEN `_poll_suspended_changes()` finds an orphaned "done" change with `merge_retry_count >= 3` THEN it sets status to `integration-failed` instead of re-adding to queue [REQ: merge-retry-limit-enforcement, scenario: monitor-does-not-re-add-exhausted-changes]
- [x] AC-3: WHEN a change has status "stalled" AND loop-state.json shows "done" THEN the monitor recovers it to "done" and adds to merge queue [REQ: stalled-changes-with-completed-work-are-recovered, scenario: stalled-change-with-loop-state-done-is-recovered]
- [x] AC-4: WHEN `set-merge --ff-only` is called with a valid worktree branch THEN the merge succeeds with exit code 0 [REQ: ff-only-merge-resolves-worktree-branch-correctly, scenario: ff-only-merge-succeeds-for-worktree-branch]
- [x] AC-5: WHEN integration e2e gate generates `playwright-report/` and `test-results/` THEN these do NOT appear as dirty in `git status` [REQ: web-template-includes-comprehensive-gitignore, scenario: playwright-artifacts-are-gitignored]
