# Tasks: shodh-memory-gui

## 1. Per-project storage in set-memory CLI

- [x] 1.1 Add `resolve_project()` function: detect project name from `git rev-parse --show-toplevel` basename, fall back to `_global`
- [x] 1.2 Add `--project` flag override to all commands (remember, recall, status, list) — parsed in `main()` before dispatch
- [x] 1.3 Update `cmd_remember` to use `$SHODH_STORAGE/$project/` as storage path
- [x] 1.4 Update `cmd_recall` to use `$SHODH_STORAGE/$project/` as storage path
- [x] 1.5 Update `cmd_status` to show resolved project name and per-project path; add `--json` flag outputting `{"available": bool, "project": str, "count": int, "storage_path": str}`
- [x] 1.6 Add `cmd_list` to output all memories for current project as JSON array (uses `Memory.list_memories()`)
- [x] 1.7 Add `cmd_projects` to list all project directories with memory counts
- [x] 1.8 Handle legacy storage: detect old-format files (`.sst` files) in root, treat as `_legacy` project

## 2. Project header [M] button

- [x] 2.1 Add `get_memory_status(project)` helper in table.py — runs `set-memory status --json --project <name>` via subprocess, parses JSON result `{"available", "count"}`. Returns `{"available": False, "count": 0}` on any error.
- [x] 2.2 Add [M] button to `_create_project_header` after existing chat button: purple (`status_compacting`) when available+count>0, gray (`status_idle`) when not installed or count==0
- [x] 2.3 Add tooltip showing "Memory: N memories" or "Memory: not installed"
- [x] 2.4 Connect button click to open memory browse dialog, passing `project` name

## 3. Project header context menu

- [x] 3.1 Store project header row mapping in `row_to_project` dict during `render_worktrees` — map header row index to `proj_name` string
- [x] 3.2 In `show_row_context_menu`, before the `row_to_worktree` check: look up `row_to_project[row]` and if found dispatch to `show_project_header_context_menu(pos, project)`. Remove the early `return` at line 143.
- [x] 3.3 Implement `show_project_header_context_menu(pos, project)` with: Memory submenu, separator, + New Worktree, Team Chat, Team Settings, Initialize wt-control
- [x] 3.4 Memory submenu: disabled status line (from `get_memory_status`), Browse Memories action, Remember Note action. Disable Browse and Remember when `available` is False.
- [x] 3.5 Memory submenu SKILL.md check: find main repo path via `get_main_repo_path(first_wt_path_for_project)`, grep `.claude/skills/openspec-*/SKILL.md` for "set-memory". Show disabled warning "OpenSpec skills not hooked" if no match.

## 4. Memory browse dialog

- [x] 4.1 Create `gui/dialogs/memory_dialog.py` with `MemoryBrowseDialog(QDialog)` — takes `project: str` in constructor
- [x] 4.2 Initial load: run `set-memory list --project X` via subprocess, parse JSON array, populate list widget with content preview, type badge, tags, creation date
- [x] 4.3 Search field: on Enter, run `set-memory recall --project X "query"` via subprocess, replace list contents with search results. On clear, reload full list via `set-memory list`.
- [x] 4.4 Handle empty state: "No memories yet" message when list returns `[]`
- [x] 4.5 Set `WindowStaysOnTopHint` per project dialog conventions

## 5. Remember note dialog

- [x] 5.1 Create `RememberNoteDialog(QDialog)` in `gui/dialogs/memory_dialog.py` — takes `project: str` in constructor
- [x] 5.2 Content text area, type dropdown (Learning, Decision, Observation, Event), tags input field
- [x] 5.3 Save button calls `set-memory remember --type X --tags Y --project Z` via subprocess (pipe content via stdin)
- [x] 5.4 Set `WindowStaysOnTopHint` per project dialog conventions

## 6. OpenSpec SKILL.md memory hooks

- [x] 6.1 Modify `openspec-new-change/SKILL.md`: add recall step after user description — `set-memory recall "description keywords"` (no explicit health check needed, CLI handles graceful degradation)
- [x] 6.2 Modify `openspec-continue-change/SKILL.md`: add recall step before acting on status
- [x] 6.3 Modify `openspec-ff-change/SKILL.md`: add recall step before artifact creation loop
- [x] 6.4 Modify `openspec-apply-change/SKILL.md`: add recall step before implementing, remember step after (errors as Observation, patterns as Learning, completion as Event)
- [x] 6.5 Modify `openspec-archive-change/SKILL.md`: add remember step for decisions, learnings, and completion event

## 7. GUI tests

- [x] 7.1 Add `tests/gui/test_XX_memory.py` with tests for [M] button rendering in project header
- [x] 7.2 Test project header context menu opens (right-click on header row dispatches to `show_project_header_context_menu`)
- [x] 7.3 Test memory browse dialog instantiation and empty state
