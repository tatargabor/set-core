## 1. Hooks — stop.sh transcript extraction (CRITICAL data loss)

- [x] 1.1 Fix `_stop_raw_filter` heredoc: pass transcript path via `TRANSCRIPT_PATH` env var instead of `sys.argv[1]`
- [x] 1.2 Fix `STOP_LOCK_FILE`/`STOP_LOG_FILE` relative paths — derive from project root at point of use
- [x] 1.3 Add `stop.sh` to `events.sh` dependency comment header
- [x] 1.4 Initialize `_LAST_CONTEXT_IDS=""` in `memory-ops.sh` global scope
- [x] 1.5 Clear `$TMPFILE` at start of `recall_and_format` and `proactive_and_format` to prevent stale data
- [x] 1.6 Add `sys.exit(1)` guard in `recall_and_format` Python block when all memories filtered (match `proactive_and_format` pattern)

## 2. Memory — cmd_repair, cmd_seed, locking

- [x] 2.1 Add `cmd_repair` function to `lib/memory/maintenance.sh`
- [x] 2.2 Fix `cmd_seed` in `lib/memory/ui.sh`: change `cmd_recall --query "$content"` to positional `cmd_recall "$content"`
- [x] 2.3 Wrap `cmd_projects` RocksDB access with `run_with_lock` in `lib/memory/maintenance.sh`
- [x] 2.4 Replace bare `python3` with `"$SHODH_PYTHON"` in `lib/memory/core.sh:88` metadata validation
- [x] 2.5 Fix unknown flags silently swallowed in `cmd_sync` — error on `-*)`
- [x] 2.6 Remove orphan comment stubs at end of `rules.sh`, `todos.sh`, `core.sh` (copy-paste remnants)
- [x] 2.7 Fix typo "unmigrared" → "unmigrated" in `maintenance.sh`
- [x] 2.8 Add `_wt_memory_bin_dir` dependency comment to `ui.sh` header
- [x] 2.9 Guard `AUTO_MIGRATE_DONE`/`NO_MIGRATE` in `migrate.sh` with `${VAR:-false}` pattern

## 3. Orchestration — scope and undefined variable fixes

- [x] 3.1 Fix `dispatcher.sh:680`: pass `"$INPUT_PATH"` to `parse_directives`
- [x] 3.2 Fix `dispatcher.sh:687`: remove extra `"$directives_for_gate"` arg from `init_state` call
- [x] 3.3 Define `PROJECT_PATH` global in `bin/set-orchestrate` main() — `PROJECT_PATH=$(pwd)`
- [x] 3.4 Fix `verifier.sh` `smoke_fix_scoped`: read `test_command` from `$STATE_FILENAME` instead of `$directives` local
- [x] 3.5 Fix `merger.sh` smoke variables: read `smoke_command`, `smoke_blocking`, `smoke_timeout` etc. from `$STATE_FILENAME` instead of relying on `monitor_loop` locals
- [x] 3.6 Remove dangling "Duration Parsing" comment block from `config.sh` (lines 48-53)
- [x] 3.7 Remove orphan `orch_remember` comment stub from `state.sh` (lines 271-272)
- [x] 3.8 Fix `send_notification` urgency `"warning"` → `"normal"` in `verifier.sh` (3 call sites)

## 4. Loop — engine, state, tasks, prompt fixes

- [x] 4.1 Fix `init_loop_state` JSON injection: escape `label` and `change` fields with `jq -Rs .`
- [x] 4.2 Remove debug `warn` from `check_done` in `tasks.sh:169`
- [x] 4.3 Fix `cmd_list` hard-coded state file path — use `get_loop_state_file` instead
- [x] 4.4 Fix `allowedTools` permission flag: use `eval` at call site in `engine.sh` with safety comment
- [x] 4.5 Add `[[ -n "$state_file" ]]` guard in `cleanup_on_exit` before `update_loop_state` call
- [x] 4.6 Fix `detect_next_change_action` scan path: check archive directory for missing change_dirs

## 5. Project — deploy.sh coupling and lookup fixes

- [x] 5.1 Move `_register_mcp_server` and `_cleanup_deprecated_memory_refs` from `set-project` into `deploy.sh`
- [x] 5.2 Add runtime guard for `SCRIPT_DIR` and `WT_TOOLS_ROOT` at top of `deploy.sh`
- [x] 5.3 Fix `_save_project_type` project lookup: use path-based lookup instead of `basename`
- [x] 5.4 Add comment explaining `gui` subdirectory skip in rules deployment

## 6. Tests

- [x] 6.1 Add unit test for `cmd_repair` (verify it runs without error)
- [x] 6.2 Add unit test for `init_loop_state` with special characters in label
- [x] 6.3 Run all existing unit tests to verify no regressions (38/38 pass)
