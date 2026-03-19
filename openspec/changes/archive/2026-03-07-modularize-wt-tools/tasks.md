## 1. Test Infrastructure

- [x] 1.1 Create `tests/unit/helpers.sh` with assert_equals, assert_contains, assert_exit_code, test runner
- [x] 1.2 Verify helpers work with a trivial self-test

## 2. Phase 1 — wt-common.sh Editor Extract

- [x] 2.1 Create `lib/editor.sh` — move all 19 editor functions from wt-common.sh
- [x] 2.2 Update `bin/wt-common.sh` — remove editor functions, auto-source lib/editor.sh for backward compat
- [x] 2.3 All 6 editor-using scripts work via auto-source (wt-config, wt-work, wt-new, wt-focus, wt-loop, wt-status)
- [x] 2.4 Create `tests/unit/test_editor.sh` — test key editor detection functions
- [x] 2.5 Run existing tests to verify no regressions (35/35 pass)

## 3. Phase 2 — set-memory Split

- [x] 3.1 Create `lib/memory/core.sh` — extract cmd_remember, cmd_recall, cmd_proactive, cmd_list, cmd_get, cmd_forget, cmd_export, cmd_import, cmd_context, cmd_brain
- [x] 3.2 Create `lib/memory/maintenance.sh` — extract cmd_stats, cmd_cleanup, cmd_audit, cmd_dedup, cmd_verify, cmd_consolidation, cmd_graph_stats, cmd_flush, cmd_repair, cmd_cleanup_logs, cmd_health, cmd_status, cmd_projects
- [x] 3.3 Create `lib/memory/rules.sh` — extract get_rules_file, _rules_make_id, _rules_match, cmd_rules, cmd_rules_add, cmd_rules_list, cmd_rules_remove
- [x] 3.4 Create `lib/memory/todos.sh` — extract cmd_todo, cmd_todo_add, cmd_todo_list, cmd_todo_done, cmd_todo_clear
- [x] 3.5 Create `lib/memory/sync.sh` — extract sync_resolve_identity, _sync_work_dir, sync_get_state, sync_update_state, sync_check_preconditions, cmd_sync_push, cmd_sync_pull, cmd_sync, cmd_sync_status
- [x] 3.6 Create `lib/memory/migrate.sh` — extract migrations_read, migrations_write, migration_is_applied, migration_mark_applied, migrate_001_branch_tags, run_migrations, auto_migrate, cmd_migrate
- [x] 3.7 Create `lib/memory/ui.sh` — extract cmd_metrics, cmd_tui, cmd_dashboard, cmd_seed
- [x] 3.8 Refactor `bin/set-memory` — keep infra + dispatcher (3713 → 377 lines), sources lib/memory/*.sh
- [x] 3.9 Create `tests/unit/test_memory_sync.sh` — test sync state helpers (3 tests)
- [x] 3.10 Create `tests/unit/test_memory_migrate.sh` — test migration framework (3 tests)
- [x] 3.11 Run `set-memory health`, `set-memory recall test`, `set-memory rules list` — all pass

## 4. Phase 3 — wt-hook-memory Split

- [x] 4.1 Create `lib/hooks/util.sh` — extract logging, metrics timers, score extraction (154 lines)
- [x] 4.2 Create `lib/hooks/session.sh` — extract dedup cache, context IDs (134 lines)
- [x] 4.3 Create `lib/hooks/memory-ops.sh` — extract recall, proactive, rules, output (372 lines)
- [x] 4.4 Create `lib/hooks/events.sh` — extract all 9 event handlers (727 lines)
- [x] 4.5 Create `lib/hooks/stop.sh` — extract metrics flush, transcript extraction (410 lines)
- [x] 4.6 Refactor `bin/wt-hook-memory` — thin dispatcher (1817 → 55 lines)
- [x] 4.7 Create `tests/unit/test_hook_session.sh` — test dedup and context ID (2 tests)
- [x] 4.8 Hooks work end-to-end (syntax check + unknown event test pass)

## 5. Phase 4 — Orchestration Refactor

- [x] 5.1 Create `lib/orchestration/config.sh` — extract wt_find_config, wt_find_runs_dir, wt_find_requirements_dir from state.sh
- [x] 5.2 Create `lib/orchestration/orch-memory.sh` — extract orch_remember, orch_recall, orch_recall_by_date from state.sh
- [x] 5.3 Create `lib/orchestration/utils.sh` — extract parse_duration, format_duration, brief_hash, parse_directives, parse_next_items from state.sh
- [x] 5.4 Refactor `lib/orchestration/state.sh` — keep jq state operations only (~400 lines)
- [x] 5.5 Create `lib/orchestration/builder.sh` — extract check_base_build, fix_base_build_with_llm from dispatcher.sh
- [x] 5.6 Create `lib/orchestration/monitor.sh` — extract monitor_loop, poll_change, dispatch_queued_changes from dispatcher.sh
- [x] 5.7 Refactor `lib/orchestration/dispatcher.sh` — keep dispatch/resume/pause core (~350 lines)
- [x] 5.8 Update merger.sh — use builder.sh instead of duplicated BASE_BUILD_* logic (resolved: builder.sh sourced before merger.sh, no duplication)
- [x] 5.9 Update `bin/set-orchestrate` — adjust source order for new modules
- [x] 5.10 Create `tests/unit/test_orch_state.sh` — test state query functions
- [x] 5.11 Run orchestration integration tests

## 6. Phase 5 — wt-loop Split

- [x] 6.1 Create `lib/loop/state.sh` — extract state management functions (get_loop_state_file, init_loop_state, update_loop_state, add_iteration, get_current_tokens, estimate_tokens_from_files)
- [x] 6.2 Create `lib/loop/tasks.sh` — extract task detection (count_manual_tasks, parse_manual_tasks, check_tasks_done, generate_fallback_tasks, check_done)
- [x] 6.3 Create `lib/loop/prompt.sh` — extract prompt building (detect_next_change_action, build_prompt)
- [x] 6.4 Create `lib/loop/engine.sh` — extract cmd_run() refactored
- [x] 6.5 Refactor `bin/wt-loop` — keep CLI commands + main dispatcher, source lib/loop/*.sh
- [x] 6.6 Create `tests/unit/test_loop_tasks.sh` — test task detection modes
- [x] 6.7 Run `wt-loop status` and existing loop tests to verify

## 7. Phase 6 — set-project Deploy Refactor

- [x] 7.1 Split deploy_set_tools() into deploy_hooks(), deploy_commands(), deploy_skills(), deploy_mcp(), deploy_memory()
- [x] 7.2 Update cmd_init() to call the new focused functions
- [x] 7.3 Run `set-project init` on a test project to verify

## 8. Documentation

- [x] 8.1 Add source-order and dependency header comments to all extracted modules
- [x] 8.2 Update docs/design/modularization-plan.md with completion notes
