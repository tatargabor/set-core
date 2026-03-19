# Tasks: migrate-runtime-to-dot-wt

## 1. Path resolution infrastructure

- [x] 1.1 Create `lib/wt_orch/paths.py` with `WtRuntime` class — resolves to `~/.local/share/wt-tools/<project>/`. Properties: state_file, events_file, plans_dir, runs_dir, digest_dir, sentinel_dir, sentinel_pid, logs_dir, change_logs_dir(change), screenshots_dir, cache_dir, design_snapshot, version. Static method: `agent_dir(worktree_path)` for per-worktree `.wt/`. Uses git rev-parse for project name resolution (same as memory system). [REQ: path-resolution-via-config-constant, shared-runtime-directory]
- [x] 1.2 Create `bin/wt-paths` sourceable bash helper exporting: `$WT_RUNTIME_DIR`, `$WT_STATE_FILE`, `$WT_EVENTS_FILE`, `$WT_SENTINEL_DIR`, `$WT_LOGS_DIR`, `$WT_AGENT_DIR` (relative `.wt`). Project name resolved via git. [REQ: path-resolution-via-config-constant]
- [x] 1.3 Add unit tests for WtRuntime (path generation, project name resolution, XDG_DATA_HOME override, worktree detection) [REQ: path-resolution-via-config-constant]

## 2. Orchestration runtime migration

- [x] 2.1 Update `lib/wt_orch/engine.py` — use WtRuntime for state.json, events.jsonl, plans/, and the hardcoded `.claude/loop-state.json` agent queries [REQ: orchestration-runtime-migration]
- [x] 2.2 Update `lib/wt_orch/dispatcher.py` — use WtRuntime for state.json; use `WtRuntime.agent_dir()` for worktree bootstrap; update `bootstrap_worktree()` to create `<worktree>/.wt/` [REQ: orchestration-runtime-migration]
- [x] 2.3 Update `lib/wt_orch/verifier.py` — use WtRuntime for spec-coverage-report.md and screenshot paths [REQ: orchestration-runtime-migration]
- [x] 2.4 Update `lib/wt_orch/merger.py` — use WtRuntime for state.json; archive logs to `WtRuntime.change_logs_dir(change)` instead of `wt/orchestration/logs/`; respect worktree_retention config [REQ: orchestration-runtime-migration, worktree-retention]
- [x] 2.5 Update `lib/wt_orch/planner.py` — use WtRuntime for plans/ and state.json [REQ: orchestration-runtime-migration]
- [x] 2.6 Update `lib/wt_orch/websocket.py` — use WtRuntime for state.json file watch path [REQ: orchestration-runtime-migration]
- [x] 2.7 Update `lib/wt_orch/events.py` — use WtRuntime for events file resolution, remove dual legacy/new path logic [REQ: orchestration-runtime-migration]
- [x] 2.8 Update `lib/wt_orch/state.py` — use WtRuntime, remove hardcoded "orchestration-state.json" name [REQ: orchestration-runtime-migration]
- [x] 2.9 Update `lib/wt_orch/logging_config.py` — use WtRuntime for orchestration.log path [REQ: log-migration]
- [x] 2.10 Update `lib/wt_orch/digest.py` — use WtRuntime for digest directory [REQ: orchestration-runtime-migration]
- [x] 2.11 Update `lib/wt_orch/auditor.py` — use WtRuntime for audit-cycle-*.log paths [REQ: orchestration-runtime-migration]
- [x] 2.12 Update `lib/wt_orch/reporter.py` — use WtRuntime for report.html output path [REQ: orchestration-runtime-migration]
- [x] 2.13 Update `lib/wt_orch/milestone.py` — respect worktree_retention config in cleanup [REQ: worktree-retention]

## 3. Agent runtime migration (per-worktree)

- [x] 3.1 Update `lib/loop/state.sh` — `get_loop_state_file()` and `get_loop_log_dir()` return `.wt/` paths (must be done FIRST since wt-loop sources this) [REQ: agent-runtime-migration]
- [x] 3.2 Update `bin/wt-loop` — source wt-paths, use `.wt/` paths for loop-state.json, activity.json, reflection.md [REQ: agent-runtime-migration]
- [x] 3.3 Update `bin/wt-sentinel` — source wt-paths, use WtRuntime sentinel_pid path (shared, not per-worktree) [REQ: agent-runtime-migration]
- [x] 3.4 Update `bin/wt-merge` — use WtRuntime for state file; use `.wt/` for generated file patterns (loop-state, activity) [REQ: agent-runtime-migration]
- [x] 3.5 Update `bin/wt-new` — create `.wt/` structure in new worktrees [REQ: agent-runtime-migration]
- [x] 3.6 Update `lib/wt_orch/loop_state.py` — `get_loop_state_file()`, `get_terminal_pid_file()`, `get_loop_log_dir()`, `get_activity_file()` return `.wt/` paths [REQ: agent-runtime-migration]
- [x] 3.7 Update `lib/wt_orch/loop_tasks.py` — state file references via WtRuntime [REQ: agent-runtime-migration]
- [x] 3.8 Update `lib/wt_orch/watchdog.py` — loop-state monitoring via `.wt/` paths [REQ: agent-runtime-migration]
- [x] 3.9 Audit and update `lib/orchestration/state.sh` — use wt-paths for loop-state queries [REQ: agent-runtime-migration]
- [x] 3.10 Update `lib/orchestration/utils.sh` — loop-state detection paths [REQ: agent-runtime-migration]
- [x] 3.11 Update `lib/orchestration/dispatcher.sh` — loop-state queries [REQ: agent-runtime-migration]
- [x] 3.12 Update `.claude/hooks/activity-track.sh` — activity.json path to `.wt/activity.json` [REQ: agent-runtime-migration]
- [x] 3.13 Update `mcp-server/statusline.sh` — loop-state reads from `.wt/` [REQ: agent-runtime-migration]

## 4. Sentinel migration (from `.wt/sentinel/` to shared)

- [x] 4.1 Update `lib/wt_orch/sentinel/wt_dir.py` — `ensure_wt_dir()` → `ensure_sentinel_dir()`, resolve to `WtRuntime.sentinel_dir` instead of `.wt/sentinel/` [REQ: sentinel-migration]
- [x] 4.2 Update `lib/wt_orch/sentinel/events.py` — use WtRuntime.sentinel_dir [REQ: sentinel-migration]
- [x] 4.3 Update `lib/wt_orch/sentinel/findings.py` — use WtRuntime.sentinel_dir [REQ: sentinel-migration]
- [x] 4.4 Update `lib/wt_orch/sentinel/status.py` — use WtRuntime.sentinel_dir [REQ: sentinel-migration]
- [x] 4.5 Update `lib/wt_orch/sentinel/inbox.py` — use WtRuntime.sentinel_dir [REQ: sentinel-migration]
- [x] 4.6 Update `lib/wt_orch/sentinel/rotation.py` — use WtRuntime.sentinel_dir [REQ: sentinel-migration]
- [x] 4.7 Update sentinel API endpoints in `lib/wt_orch/api.py` — sentinel file reads via WtRuntime [REQ: sentinel-migration]
- [x] 4.8 Update `bin/wt-sentinel-inbox` — sentinel inbox path via WtRuntime [REQ: sentinel-migration]
- [x] 4.9 Update sentinel tests in `tests/unit/test_sentinel_events.py` — adjust expected paths [REQ: sentinel-migration]

## 5. Log migration

- [x] 5.1 Update orchestration log writer — use WtRuntime for logs/orchestration.log [REQ: log-migration]
- [x] 5.2 Update ralph loop log writer — current run logs to `<worktree>/.wt/logs/`, archived to WtRuntime.change_logs_dir(change) on merge [REQ: log-migration]

## 6. Cache migration

- [x] 6.1 Update codemap caching to use WtRuntime.cache_dir/codemaps/ [REQ: cache-migration]
- [x] 6.2 Update design caching to use WtRuntime.cache_dir/designs/ [REQ: cache-migration]
- [x] 6.3 Update memory commit tracker to use WtRuntime.cache_dir/last-memory-commit [REQ: cache-migration]
- [x] 6.4 Update skill invocation cache to use WtRuntime.cache_dir/skill-invocations/ [REQ: cache-migration]

## 7. Design snapshot migration

- [x] 7.1 Update design bridge fetcher (`lib/design/fetcher.py`, `lib/design/bridge.sh`) to write WtRuntime.design_snapshot [REQ: design-snapshot-migration]
- [x] 7.2 Update design bridge rule (`.claude/rules/design-bridge.md`) to reference new path [REQ: design-snapshot-migration]
- [x] 7.3 Update dispatch context injection (`lib/wt_orch/dispatcher.py`) to read from WtRuntime.design_snapshot [REQ: design-snapshot-migration]
- [x] 7.4 Update verifier design review (`lib/wt_orch/verifier.py`) to read from WtRuntime.design_snapshot [REQ: design-snapshot-migration]
- [x] 7.5 Update planner design injection (`lib/wt_orch/planner.py`) to read from WtRuntime.design_snapshot [REQ: design-snapshot-migration]

## 8. wt-web, MCP, GUI updates

- [x] 8.1 Update `lib/wt_orch/api.py` — use WtRuntime for all state file reads, sentinel_pid, sentinel endpoints [REQ: orchestration-runtime-migration]
- [x] 8.2 Update `lib/wt_orch/chat.py` — use WtRuntime for project path resolution [REQ: orchestration-runtime-migration]
- [x] 8.3 Update `mcp-server/wt_mcp_server.py` — use WtRuntime for state reads, activity reads [REQ: orchestration-runtime-migration]
- [x] 8.4 Update `gui/control_center/mixins/handlers.py` — loop-state I/O via `.wt/` paths [REQ: agent-runtime-migration]
- [x] 8.5 Update `gui/control_center/mixins/table.py` — loop-state reads via `.wt/` paths [REQ: agent-runtime-migration]

## 9. Deploy, bootstrap, and gitignore

- [x] 9.1 Update `lib/project/deploy.sh` (wt-project init) — create `~/.local/share/wt-tools/<project>/` structure with all subdirs [REQ: shared-runtime-directory]
- [x] 9.2 Add auto-migration in wt-project init — detect old paths (.claude/, project root, wt/orchestration/, .wt-tools/, .wt/sentinel/), move to shared location. Write `.migrated` marker on completion. [REQ: shared-runtime-directory]
- [x] 9.3 Update `bootstrap_worktree()` in dispatcher.py — create `<worktree>/.wt/` for per-agent ephemeral [REQ: agent-runtime-migration]
- [x] 9.4 Git untrack currently tracked runtime files: `git rm --cached wt/orchestration/orchestration-state.json wt/orchestration/spec-coverage-report.md` [REQ: gitignore-simplification]
- [x] 9.5 Clean up .gitignore — remove scattered runtime entries (loop-state.json, activity.json, *.pid, .claude/logs/, .claude/orchestration.log, orchestration-events.jsonl, .wt-tools/), keep only `/.wt/` for per-worktree ephemeral [REQ: gitignore-simplification]

## 10. Worktree retention

- [x] 10.1 Add `worktree_retention` config key to orchestration.yaml schema (values: keep, auto-clean-after-Nd, delete-on-merge; default: keep) [REQ: worktree-retention]
- [x] 10.2 Update `merger.py::cleanup_worktree()` — skip worktree+branch deletion when retention != delete-on-merge; still archive logs [REQ: worktree-retention]
- [x] 10.3 Update `merger.py::cleanup_all_worktrees()` — same retention-aware behavior [REQ: worktree-retention]
- [x] 10.4 Add `wt-cleanup` command for manual/cron GC — `wt-cleanup --older-than 7d` removes worktrees for merged changes older than N days [REQ: worktree-retention]

## 11. Skill and prompt updates

- [x] 11.1 Update skill prompts referencing `.claude/` runtime files to use `.wt/` (per-worktree) or `~/.local/share/` (shared) paths [REQ: agent-runtime-migration]
- [x] 11.2 Update hook scripts reading runtime state to use new paths [REQ: agent-runtime-migration]
- [x] 11.3 Update `.claude/commands/wt/sentinel.md` to reference shared sentinel dir [REQ: sentinel-migration]

## Acceptance Criteria

- [x] AC-1: WHEN any wt-tools component writes shared runtime data THEN it goes to `~/.local/share/wt-tools/<project>/` [REQ: shared-runtime-directory]
- [x] AC-2: WHEN orchestration engine reads/writes state THEN uses `~/.local/share/wt-tools/<project>/orchestration/state.json` [REQ: orchestration-runtime-migration]
- [x] AC-3: WHEN orchestration engine appends events THEN uses shared events.jsonl [REQ: orchestration-runtime-migration]
- [x] AC-4: WHEN ralph loop reads/writes loop state THEN uses `<worktree>/.wt/loop-state.json` [REQ: agent-runtime-migration]
- [x] AC-5: WHEN agent activity recorded THEN uses `<worktree>/.wt/activity.json` [REQ: agent-runtime-migration]
- [x] AC-6: WHEN orchestration events logged THEN written to shared logs/orchestration.log [REQ: log-migration]
- [x] AC-7: WHEN design bridge fetches snapshot THEN writes to shared design-snapshot.md [REQ: design-snapshot-migration]
- [x] AC-8: WHEN Python code needs shared runtime path THEN uses WtRuntime methods [REQ: path-resolution-via-config-constant]
- [x] AC-9: WHEN Python code needs per-agent path THEN uses WtRuntime.agent_dir(worktree_path) [REQ: path-resolution-via-config-constant]
- [x] AC-10: WHEN sentinel writes events/findings THEN uses shared sentinel dir [REQ: sentinel-migration]
- [x] AC-11: WHEN change merged with retention=keep THEN worktree and branch preserved [REQ: worktree-retention]
- [x] AC-12: WHEN ralph iteration logs archived on merge THEN copied to shared logs/changes/{change}/ [REQ: log-migration]
- [x] AC-13: WHEN migration complete THEN old scattered .gitignore patterns removable [REQ: gitignore-simplification]
