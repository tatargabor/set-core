## 1. Core lookup function

- [x] 1.1 Add `wt_find_config()` function to `lib/orchestration/state.sh` that implements the fallback chain: `wt/` location → legacy location → empty. This replaces the existing `find_project_knowledge_file()` in `planner.sh` and the hardcoded `CONFIG_FILE` in `set-orchestrate` line 29
- [x] 1.2 Add `wt_find_runs_dir()` function that returns `wt/orchestration/runs/` or `docs/orchestration-runs/` or empty
- [x] 1.3 Add `wt_find_requirements_dir()` function that returns `wt/requirements/` or empty

## 2. Update orchestration modules to use lookup functions

- [x] 2.1 Update `set-orchestrate` line 29 (`CONFIG_FILE=".claude/orchestration.yaml"`) to use `wt_find_config orchestration`, and update `state.sh` `load_config_file()` to accept the resolved path
- [x] 2.2 Replace `find_project_knowledge_file()` in `planner.sh` (lines 342-350) with `wt_find_config project-knowledge` — this function is also called by dispatcher.sh and verifier.sh
- [x] 2.3 Update `dispatcher.sh` project-knowledge injection to use `wt_find_config project-knowledge`
- [x] 2.4 Update `verifier.sh` verification rules loading to use `wt_find_config project-knowledge`
- [x] 2.5 Run log writing — N/A: run logs are manually created, not written by orchestrator code. `wt_find_runs_dir()` is available for future use

## 3. Scaffold wt/ directory in set-project init

- [x] 3.1 Add `scaffold_wt_directory()` function to `bin/set-project` that creates `wt/` subdirectories with `mkdir -p` (including `wt/.work/` and `wt/plugins/`)
- [x] 3.2a Add `wt/.work/` to project `.gitignore` if not already present
- [x] 3.2 Add legacy file detection: check for `.claude/orchestration.yaml`, `project-knowledge.yaml`, `docs/orchestration-runs/`
- [x] 3.3 Print migration suggestions when legacy files are found
- [x] 3.4 Call `scaffold_wt_directory` from `deploy_set_tools()` after `.claude/` deployment

## 4. Migrate command

- [x] 4.1 Add `cmd_migrate()` function to `bin/set-project` — moves files from legacy to `wt/` locations using `git mv` (or `mv` for non-git)
- [x] 4.2 Handle orchestration.yaml migration: `.claude/orchestration.yaml` → `wt/orchestration/config.yaml`
- [x] 4.3 Handle project-knowledge migration: `./project-knowledge.yaml` → `wt/knowledge/project-knowledge.yaml`
- [x] 4.4 Handle run logs migration: `docs/orchestration-runs/*` → `wt/orchestration/runs/`
- [x] 4.5 Add `migrate` to the case statement in `bin/set-project` main dispatcher and update `usage()` help text
- [x] 4.6 Update `cmd_init_knowledge()` to write to `wt/knowledge/project-knowledge.yaml` when `wt/` exists, fallback to project root
- [x] 4.7 Update `_migrate_consumer()` to use `wt_find_config orchestration` for directive migration (currently hardcodes `.claude/orchestration.yaml`)

## 5. Plan history saving

- [x] 5.1 Update `planner.sh` to save a copy of each plan to `wt/orchestration/plans/plan-v{N}-{date}.json` when `wt/orchestration/plans/` exists
- [x] 5.2 Preserve existing `orchestration-plan.json` as the working file (no change to existing behavior)

## 6. Requirements as planner input

- [x] 6.1 Update `planner.sh` to scan `wt/requirements/*.yaml` for requirements with status `captured` or `planned`
- [x] 6.2 Inject requirement titles and descriptions into the decomposition prompt as additional context
- [x] 6.3 Graceful degradation: skip if `wt/requirements/` does not exist or is empty

## 7. Plugin workspace support

- [x] 7.1 Add `wt/plugins/` to the scaffolded directory structure in `scaffold_wt_directory()`
- [x] 7.2 Document plugin workspace convention: each plugin gets `wt/plugins/<name>/`, plugin controls internal structure

## 8. Memory integration

- [x] 8.1 Create `wt/knowledge/memory-seed.yaml` template in `templates/` with example seeds and format documentation
- [x] 8.2 Add seed import logic to `set-project init`: check if memory store is empty + seed file exists → auto-import with `source:seed` tag
- [x] 8.3 Add `set-memory seed` command: import from `wt/knowledge/memory-seed.yaml` with content-hash duplicate detection
- [x] 8.4 Update `set-memory sync push` to use `wt/.work/memory/` for export and sync-state when `wt/` exists (fallback to current behavior)
- [x] 8.5 Update `set-memory sync pull` to use `wt/.work/memory/import-staging/` when `wt/` exists
- [x] 8.6 Add legacy `.sync-state` migration: on first sync with `wt/` present but no `wt/.work/memory/.sync-state`, copy from legacy storage path

## 9. Testing

- [x] 9.1 Test `wt_find_config` fallback chain: new location wins, legacy works, missing returns empty
- [x] 9.2 Test `set-project init` creates `wt/` structure (including `wt/plugins/`, `wt/.work/`) and detects legacy files
- [x] 9.3 Test `set-project migrate` moves files correctly
- [x] 9.4 Test planner reads requirements from `wt/requirements/`
- [x] 9.5 Test `set-memory seed` imports from seed file with duplicate detection
- [x] 9.6 Test `set-project init` auto-imports seeds when memory store is empty
