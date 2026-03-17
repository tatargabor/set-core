## 1. Close flock fd in sentinel child spawn (Bug #41)

- [x] 1.1 In `bin/wt-sentinel` L455, change `"$SCRIPT_DIR/wt-orchestrate" start "$@" &` to `"$SCRIPT_DIR/wt-orchestrate" start "$@" 9>&- &`

## 2. Reinstall deps after worktree sync (Bug #29/#33)

- [x] 2.1 In `lib/wt_orch/dispatcher.py`, add helper function `_reinstall_deps_if_needed(wt_path: str, old_sha: str, new_sha: str) -> None` that: (a) diffs old_sha..new_sha for lockfile/package.json changes, (b) if found, runs PM install via `_detect_package_manager`, (c) logs result, non-blocking on failure
- [x] 2.2 In `sync_worktree_with_main()`, after the successful merge (L217) AND after the auto-resolved conflict path (L320), call `_reinstall_deps_if_needed(wt_path, merge_base, main_head)`

## 3. Update bug index status in READMEs

- [x] 3.1 In `tests/e2e/minishop/README.md`: update Bug #24, #29, #33, #37, #38, #41 statuses
- [x] 3.2 In `tests/e2e/craftbrew/README.md`: update Bug #9 status to "fixed (`eec894bcb`)"
