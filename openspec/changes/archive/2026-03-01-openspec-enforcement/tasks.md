## 1. Pre-dispatch Artifact Validation

- [x] 1.1 In `bin/set-orchestrate` `dispatch_change()`, after proposal pre-creation, check if `openspec/changes/<name>/tasks.md` exists in the worktree
- [x] 1.2 Log artifact status: "Artifacts ready — starting apply" or "No tasks.md — first iteration will create artifacts"

## 2. Auto-archive After Merge

- [x] 2.1 Create `archive_change()` function in `bin/set-orchestrate`: move `openspec/changes/<name>/` to `openspec/changes/archive/<YYYY-MM-DD>-<name>/`, git add + commit
- [x] 2.2 Skip archive if change directory doesn't exist (no warning)
- [x] 2.3 Wrap in error handler: log warning on failure, don't block orchestration
- [x] 2.4 Call `archive_change()` from `merge_change()` after successful merge and push

## 3. Stale Change Detection

- [x] 3.1 In `cmd_start()`, scan `openspec/changes/` excluding `archive/` and hidden dirs
- [x] 3.2 Compare directory names against current plan's change names
- [x] 3.3 For each orphan, check if an active worktree exists (via `find_existing_worktree`)
- [x] 3.4 Emit `log_warn` for each orphan with no matching plan entry or worktree
