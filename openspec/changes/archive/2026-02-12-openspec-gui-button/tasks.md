# Tasks: openspec-gui-button

## 1. wt-openspec CLI

- [x] 1.1 Create `bin/wt-openspec` bash script with usage/help, `--project` flag, and `resolve_project()` (same pattern as `set-memory`)
- [x] 1.2 Implement `cmd_status`: filesystem-based checks — `openspec/config.yaml` exists, count `openspec/changes/*/` dirs (excluding `archive`), check `.claude/skills/openspec-*` dirs. Support `--json` flag.
- [x] 1.3 Implement `cmd_init`: check `openspec` CLI exists (`which openspec`), check not already initialized, run `openspec init --tools claude` in main repo
- [x] 1.4 Implement `cmd_update`: check `openspec` CLI exists, check already initialized, run `openspec update` in main repo
- [x] 1.5 Test CLI: `wt-openspec status --json` returns correct JSON in this repo, `wt-openspec status` shows human-readable output

## 2. FeatureWorker background thread

- [x] 2.1 Create `gui/workers/feature.py` with `FeatureWorker(QThread)`: `features_updated = Signal(dict)`, poll interval 15s, `_running` flag, `stop()` method
- [x] 2.2 Implement `_poll_project(project, main_repo_path)`: run `set-memory status --json --project X` and `wt-openspec status --json` (with cwd=main_repo), return combined dict `{"memory": {...}, "openspec": {...}}`
- [x] 2.3 Implement `run()` loop: iterate `self._projects` list, call `_poll_project` for each, emit `features_updated` with `{project_name: {memory: ..., openspec: ...}}`. First poll runs immediately.
- [x] 2.4 Add `set_projects(projects_with_paths)` method to update the project list from StatusWorker data
- [x] 2.5 Add `refresh_now()` method that wakes the worker for an immediate poll (for post-init/update refresh)
- [x] 2.6 Export from `gui/workers/__init__.py`

## 3. Wire FeatureWorker into ControlCenter

- [x] 3.1 In `main_window.py`: create `FeatureWorker`, connect `features_updated` signal to new `on_features_updated` handler
- [x] 3.2 Implement `on_features_updated(data)`: store in `self._feature_cache = data`, call `refresh_table_display()`
- [x] 3.3 In `update_status`: extract project→main_repo_path mapping from worktree data, call `feature_worker.set_projects()`
- [x] 3.4 Stop FeatureWorker in window cleanup (same pattern as other workers)

## 4. Refactor memory [M] button to use cache

- [x] 4.1 Change `get_memory_status(project)` to read from `self._feature_cache.get(project, {}).get("memory", {"available": False, "count": 0})` — no subprocess
- [x] 4.2 Update `_create_project_header` memory button to handle "checking..." state when cache is empty
- [x] 4.3 Update `show_project_header_context_menu` memory status to read from cache

## 5. OpenSpec [O] button in project header

- [x] 5.1 Add `get_openspec_status(project)` method reading from `self._feature_cache.get(project, {}).get("openspec", {"installed": False})`
- [x] 5.2 Add [O] button in `_create_project_header` after [M]: green (`status_running`) when installed, gray (`status_idle`) when not. Tooltip shows "OpenSpec: N active changes" or "OpenSpec: not initialized".
- [x] 5.3 Connect [O] button click — for now, open context menu at button position (same as right-click)

## 6. OpenSpec context menu section

- [x] 6.1 Add "OpenSpec" submenu in `show_project_header_context_menu` after "Memory" submenu
- [x] 6.2 When installed: disabled status line ("Version: X, N active changes"), separator, "Update Skills..." action
- [x] 6.3 When not installed: disabled status line ("Not initialized"), separator, "Initialize OpenSpec..." action
- [x] 6.4 "Initialize OpenSpec..." action: run `wt-openspec init` via `CommandOutputDialog` with main repo cwd, then call `refresh_feature_cache()`
- [x] 6.5 "Update Skills..." action: run `wt-openspec update` via `CommandOutputDialog` with main repo cwd, then call `refresh_feature_cache()`
- [x] 6.6 Add `refresh_feature_cache()` method that calls `feature_worker.refresh_now()`

## 7. GUI tests

- [x] 7.1 Add `tests/gui/test_30_openspec_button.py`: test [O] button renders in project header with mocked `_feature_cache`
- [x] 7.2 Test project header context menu includes "OpenSpec" submenu
- [x] 7.3 Test FeatureWorker instantiation and signal emission (mock subprocess)
- [x] 7.4 Update `tests/gui/test_29_memory.py` to mock `_feature_cache` instead of `get_memory_status` (reflect cache refactor)
