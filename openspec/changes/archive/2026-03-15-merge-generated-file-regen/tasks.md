## 1. Lock File Regeneration in wt-merge

- [x] 1.1 Add `is_lockfile()` helper in `bin/wt-merge` that checks if a filename is a lock file (using profile `lockfile_pm_map()` with hardcoded JS fallback: pnpm-lock.yaml, yarn.lock, package-lock.json)
- [x] 1.2 Add `regenerate_lockfile()` function in `bin/wt-merge` that maps a lock file name to its PM install command (via profile then fallback), runs install, and stages the regenerated file
- [x] 1.3 Update `auto_resolve_generated_files()` to call `regenerate_lockfile()` after accepting "ours" for each lock file, and emit `LOCKFILE_CONFLICTED=<filename>` to stdout
- [x] 1.4 Add profile integration: source `wt/plugins/project-type.yaml` or call profile lockfile map via a helper that reads the `.generated-file-patterns` mechanism or a new `.lockfile-pm-map` file written by `wt-project init`

## 2. Pre-Merge Runtime File Cleanup

- [x] 2.1 Add `cleanup_runtime_files()` function in `bin/wt-merge` that runs `git rm --cached` on `.wt-tools/.last-memory-commit`, `.wt-tools/agents/`, `.wt-tools/orphan-detect/` if they are tracked
- [x] 2.2 Add `.gitignore` update logic: ensure the three runtime patterns are present in `.gitignore`, appending them if missing (no duplicates)
- [x] 2.3 Call `cleanup_runtime_files()` early in the `wt-merge` flow, before the merge attempt, committing the cleanup if any files were removed

## 3. Unconditional Post-Merge Install in merger.py

- [x] 3.1 Update `_post_merge_deps_install()` to accept an optional `lockfile_conflicted: bool` parameter
- [x] 3.2 When `lockfile_conflicted=True`, skip the `package.json` change check and run install unconditionally
- [x] 3.3 Parse `LOCKFILE_CONFLICTED=` markers from `wt-merge` stdout in `merge_change()` and pass the flag to `_post_merge_deps_install()`

## 4. Worktree Sync Regeneration

- [x] 4.1 Add lock file detection to `sync_worktree_with_main()` in `dispatcher.py`: after auto-resolving generated file conflicts, check if any resolved file was a lock file
- [x] 4.2 When lock file conflict detected in sync, run the install command in the worktree directory (via `config.detect_package_manager()` or profile) before committing the merge
- [x] 4.3 Update `SyncResult` dataclass to include a `lockfile_regenerated: bool` field for observability

## 5. Testing

- [x] 5.1 Add unit tests for `is_lockfile()` and `regenerate_lockfile()` helpers (mock install command execution)
- [x] 5.2 Add unit test for `cleanup_runtime_files()` — verify correct files are removed from index, .gitignore updated
- [x] 5.3 Add unit test for `_post_merge_deps_install()` with `lockfile_conflicted=True` — verify install runs without package.json check
- [x] 5.4 Add unit test for `sync_worktree_with_main()` lock file regeneration path
- [x] 5.5 Add integration test: simulate lock file conflict in merge, verify regenerated lock file is in the merge commit
