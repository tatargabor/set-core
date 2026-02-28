## 1. Post-rebase merge verification

- [x] 1.1 In `merge_change()`, after the agent rebase loop completes (detected via `merge_rebase_pending` flag in `handle_change_done()`), attempt a test merge: `git merge-tree $(git merge-base HEAD origin/main) HEAD origin/main` or equivalent dry-run. If clean, call `merge_change()` again. If conflicts remain, set status to `merge-blocked`.
- [x] 1.2 In `handle_change_done()`, when `merge_rebase_pending` is true, clear the flag and attempt merge instead of re-entering the verify gate.

## 2. Conflict fingerprint deduplication

- [x] 2.1 In `_try_merge()`, after a failed `merge_change()`, capture the list of conflicted files via `git diff --name-only --diff-filter=U`, sort them, and store as `last_conflict_files` on the change in state.
- [x] 2.2 Before the next retry attempt in `_try_merge()`, compare the new conflict fingerprint with the stored one. If identical, log "Same conflict as previous attempt — stopping retries" and break out of the retry loop, setting status to `merge-blocked`.

## 3. Merge-blocked exclusion from completion check

- [x] 3.1 Find the "all done" check in the monitor loop (where it triggers auto-replan). Change the completion condition to only count `merged` and `done` statuses. Exclude `merge-blocked`, `failed`, and `verify-failed` from the "complete" count.
- [x] 3.2 Add a separate log line when merge-blocked changes exist: "N changes complete, M merge-blocked — not triggering replan".

## 4. Merge retry log level reduction

- [x] 4.1 In `merge_change()`, change `log_error "Merge conflict for $change_name"` to only emit ERROR on the first conflict (check `merge_retry_count == 0` or `agent_rebase_done == false`). For subsequent calls, use `log_info`.
- [x] 4.2 In `_try_merge()`, change `log_info "Merge attempt"` to include the conflict file list for diagnostics. Keep the final exhausted-retries log as `log_error`.

## 5. Post-merge dependency install

- [x] 5.1 In `merge_change()`, after a successful merge (status set to `merged`), check if `package.json` was modified in the merge diff using `git diff HEAD~1 --name-only | grep -q '^package\.json$'`.
- [x] 5.2 If `package.json` changed, auto-detect the package manager from lockfile presence (`pnpm-lock.yaml` → `pnpm install`, `yarn.lock` → `yarn install`, `package-lock.json` → `npm install`) and run it. Log the result. On failure, log a warning but do not revert the merge.
