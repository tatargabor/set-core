# Tasks: migrate-runtime-to-dot-wt

## 1. Path resolution infrastructure

- [ ] 1.1 Create `lib/wt_orch/paths.py` with `WtDirs` class — properties for all runtime paths: state_file, events_file, plans_dir, runs_dir, loop_state, activity, sentinel_pid, ralph_pid, scheduled_tasks_lock, logs_dir, cache_dir, design_snapshot, version. Instantiated with `WtDirs(project_path)`, access via `@property` [REQ: path-resolution-via-config-constant]
- [ ] 1.2 Create `bin/wt-paths` sourceable bash helper exporting: `$WT_STATE_FILE`, `$WT_EVENTS_FILE`, `$WT_LOOP_STATE_FILE`, `$WT_ACTIVITY_FILE`, `$WT_LOGS_DIR`, `$WT_SENTINEL_PID`, `$WT_RALPH_PID` [REQ: path-resolution-via-config-constant]
- [ ] 1.3 Add unit tests for WtDirs (path generation, directory creation) [REQ: path-resolution-via-config-constant]

## 2. Orchestration runtime migration

- [ ] 2.1 Update `lib/wt_orch/engine.py` — use WtDirs for state.json, events.jsonl, AND the hardcoded `.claude/loop-state.json` path (~line 561) [REQ: orchestration-runtime-migration]
- [ ] 2.2 Update `lib/wt_orch/dispatcher.py` — use WtDirs for state.json and worktree bootstrap [REQ: orchestration-runtime-migration]
- [ ] 2.3 Update `lib/wt_orch/verifier.py` — use WtDirs for spec-coverage-report.md [REQ: orchestration-runtime-migration]
- [ ] 2.4 Update `lib/wt_orch/merger.py` — use WtDirs for state.json [REQ: orchestration-runtime-migration]
- [ ] 2.5 Update `lib/wt_orch/planner.py` — use WtDirs for plans/ and state.json [REQ: orchestration-runtime-migration]
- [ ] 2.6 Update `lib/wt_orch/websocket.py` — use WtDirs for state.json file watch path [REQ: orchestration-runtime-migration]

## 3. Agent runtime migration

- [ ] 3.1 Update `bin/wt-loop` — source wt-paths, use new paths for loop-state.json, activity.json, reflection.md [REQ: agent-runtime-migration]
- [ ] 3.2 Update `bin/wt-sentinel` — source wt-paths, use new sentinel.pid path [REQ: agent-runtime-migration]
- [ ] 3.3 Update `bin/wt-merge` — use WtDirs for generated file patterns (loop-state, activity, etc.) [REQ: agent-runtime-migration]
- [ ] 3.4 Update `bin/wt-new` — create .wt/ structure in new worktrees [REQ: agent-runtime-migration]
- [ ] 3.5 Update `lib/loop/state.sh` — `get_loop_state_file()` and `get_loop_log_dir()` return .wt/agent/ and .wt/logs/ paths (must be done before 3.1 since wt-loop sources this) [REQ: agent-runtime-migration]
- [ ] 3.6 Update `lib/wt_orch/loop_state.py` — `get_loop_state_file()` and `get_loop_log_dir()` return .wt/agent/ and .wt/logs/ paths [REQ: agent-runtime-migration]
- [ ] 3.7 Audit and update `lib/orchestration/*.sh` — source wt-paths where runtime paths are referenced [REQ: agent-runtime-migration]

## 4. Log migration

- [ ] 4.1 Update orchestration log writer — use WtDirs for .wt/logs/orchestration.log [REQ: log-migration]
- [ ] 4.2 Update ralph loop log writer — use WtDirs for .wt/logs/ralph-iter-*.log paths [REQ: log-migration]

## 5. Cache migration

- [ ] 5.1 Update codemap caching to use .wt/cache/codemaps/ [REQ: cache-migration]
- [ ] 5.2 Update design caching to use .wt/cache/designs/ [REQ: cache-migration]
- [ ] 5.3 Update memory commit tracker to use .wt/cache/last-memory-commit [REQ: cache-migration]
- [ ] 5.4 Update skill invocation cache to use .wt/cache/skill-invocations/ [REQ: cache-migration]

## 6. Design snapshot migration

- [ ] 6.1 Update design bridge (preflight fetch) to write .wt/design-snapshot.md [REQ: design-snapshot-migration]
- [ ] 6.2 Update design bridge rule (.claude/rules/design-bridge.md) to reference new path [REQ: design-snapshot-migration]
- [ ] 6.3 Update dispatch context injection to read from .wt/design-snapshot.md [REQ: design-snapshot-migration]

## 7. wt-web and MCP updates

- [ ] 7.1 Update `lib/wt_orch/api.py` — use WtDirs for all state file reads AND `sentinel_pid_file` references (~lines 134, 1299-1304) [REQ: orchestration-runtime-migration]
- [ ] 7.2 Update `lib/wt_orch/chat.py` — use WtDirs for project path resolution [REQ: orchestration-runtime-migration]
- [ ] 7.3 Update `mcp-server/wt_mcp_server.py` — use WtDirs for state reads, activity reads [REQ: orchestration-runtime-migration]

## 8. Deploy and bootstrap

- [ ] 8.1 Update `lib/project/deploy.sh` (wt-project init) — create .wt/ structure, add /.wt/ to .gitignore [REQ: centralized-runtime-directory]
- [ ] 8.2 Add auto-migration in wt-project init — detect old paths, move to .wt/ atomically (write `.wt/.migrated` marker on completion so partial failures are detectable) [REQ: centralized-runtime-directory]
- [ ] 8.3 Update `bootstrap_worktree()` in dispatcher.py — create .wt/ in new worktrees [REQ: centralized-runtime-directory]
- [ ] 8.4 Clean up old .gitignore patterns after migration (remove scattered runtime entries) [REQ: gitignore-simplification]

## 9. Skill and prompt updates

- [ ] 9.1 Update skill prompts that reference .claude/ runtime files to use .wt/ paths [REQ: agent-runtime-migration]
- [ ] 9.2 Update hook scripts that read runtime state to use new paths [REQ: agent-runtime-migration]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN any wt-tools component writes runtime data and .wt/ missing THEN .wt/ created and /.wt/ in .gitignore [REQ: centralized-runtime-directory, scenario: directory-created-on-first-use]
- [ ] AC-2: WHEN orchestration engine reads/writes state THEN uses .wt/orchestration/state.json [REQ: orchestration-runtime-migration, scenario: state-file-at-new-path]
- [ ] AC-3: WHEN orchestration engine appends events THEN uses .wt/orchestration/events.jsonl [REQ: orchestration-runtime-migration, scenario: events-file-at-new-path]
- [ ] AC-4: WHEN ralph loop reads/writes loop state THEN uses .wt/agent/loop-state.json [REQ: agent-runtime-migration, scenario: loop-state-at-new-path]
- [ ] AC-5: WHEN agent activity recorded THEN uses .wt/agent/activity.json [REQ: agent-runtime-migration, scenario: activity-file-at-new-path]
- [ ] AC-6: WHEN orchestration events logged THEN written to .wt/logs/orchestration.log [REQ: log-migration, scenario: orchestration-log-at-new-path]
- [ ] AC-7: WHEN design bridge fetches snapshot THEN writes to .wt/design-snapshot.md [REQ: design-snapshot-migration, scenario: design-snapshot-at-new-path]
- [ ] AC-8: WHEN Python code needs runtime path THEN uses WtDirs methods [REQ: path-resolution-via-config-constant, scenario: python-code-uses-wtdirs]
- [ ] AC-9: WHEN migration complete THEN old scattered .gitignore patterns removable [REQ: gitignore-simplification, scenario: old-scattered-patterns-removable]
- [ ] AC-10: WHEN ralph loop writes iteration log THEN written to .wt/logs/ralph-iter-*.log [REQ: log-migration, scenario: ralph-iteration-logs-at-new-path]
