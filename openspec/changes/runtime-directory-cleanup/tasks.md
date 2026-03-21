# Tasks: Runtime Directory Cleanup

## Phase 1: Core path changes (2 critical lines)

- [x] 1.1 `lib/set_orch/paths.py:92` — change `self.root` to include `runtime/` subdirectory
- [x] 1.2 `lib/set_orch/paths.py` — add auto-migration logic in `__init__`: if old dir exists but new doesn't, `shutil.move(old, new)`
- [x] 1.3 `bin/set-paths:39` — change `WT_RUNTIME_DIR` to include `runtime/` in path + auto-migration

## Phase 2: Watcher fix (hardcoded paths → SetRuntime)

- [x] 2.1 `lib/set_orch/watcher.py` `_find_state()` — try `SetRuntime(project_path).state_file` first, keep legacy fallback
- [x] 2.2 `lib/set_orch/watcher.py` `_find_log()` — try `SetRuntime(project_path).orchestration_log` first, keep legacy fallback

## Phase 3: Shell script hardcoded paths

- [x] 3.1 `bin/set-sentinel` — archive paths use `$WT_RUNS_DIR`, `$WT_DIGEST_DIR`, `$WT_ORCHESTRATION_DIR`
- [x] 3.2 `bin/set-orchestrate` — run archive paths use set-paths variables
- [x] 3.3 `bin/set-cleanup` — already uses `$WT_STATE_FILE` from set-paths, legacy fallback OK
- [x] 3.4 `lib/orchestration/digest.sh` — `DIGEST_DIR` default uses `$WT_DIGEST_DIR`
- [x] 3.5 `lib/orchestration/reporter.sh` — report path uses `$WT_ORCHESTRATION_DIR`

## Phase 4: Python hardcoded path fix

- [x] 4.1 `lib/set_orch/auditor.py` — default `digest_dir` resolves via SetRuntime

## Phase 5: Tests

- [x] 5.1 `tests/unit/test_paths.py` — updated assertions for `runtime/` in paths + fixed `.wt` → `.set` pre-existing
- [x] 5.2 46/46 path tests pass

## Phase 6: Verify

- [ ] 6.1 set-web dashboard loads data from new runtime/ paths
- [ ] 6.2 Sentinel starts and finds runtime dirs correctly
