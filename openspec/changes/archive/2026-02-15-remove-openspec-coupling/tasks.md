## 1. Remove openspec init from wt-new and wt-add

- [x] 1.1 Remove `openspec init` block from `bin/wt-new` (lines 179-183)
- [x] 1.2 Remove `--no-openspec` flag parsing from `bin/wt-new` (skip_openspec variable, case branch)
- [x] 1.3 Remove `--no-openspec` from usage text in `bin/wt-new`
- [x] 1.4 Remove old `/openspec:*` skill references from `bin/wt-new` help text (lines ~403-409)
- [x] 1.5 Remove `openspec init` block from `bin/wt-add` (lines 291-296)
- [x] 1.6 Remove `--no-openspec` from `bin/wt-completions.bash`
- [x] 1.7 Remove `--no-openspec` from `bin/wt-completions.zsh`

## 2. Refactor wt-loop to CWD-based operation

- [x] 2.1 Add `get_worktree_path_from_cwd()` function using `git rev-parse --show-toplevel`
- [x] 2.2 Refactor `cmd_start`: remove change_id positional param, derive wt_path from CWD
- [x] 2.3 Refactor `cmd_run`: remove change_id param, derive wt_path from CWD
- [x] 2.4 Refactor `cmd_stop`: remove change_id param, derive wt_path from CWD
- [x] 2.5 Refactor `cmd_status`: remove change_id param, derive wt_path from CWD
- [x] 2.6 Refactor `cmd_history`: remove change_id param, derive wt_path from CWD
- [x] 2.7 Refactor `cmd_monitor`: remove change_id param, derive wt_path from CWD
- [x] 2.8 Remove `detect_change_id_from_pwd()` function
- [x] 2.9 Update `usage()` text to reflect new CWD-based interface
- [x] 2.10 Update `init_loop_state()`: replace `change_id` with `worktree_name` (basename of wt_path)
- [x] 2.11 Update terminal titles from `Ralph: $change_id` to `Ralph: $worktree_name`
- [x] 2.12 Update `build_prompt()` to remove change-id references

## 3. Simplify tasks.md lookup

- [x] 3.1 Rewrite `check_tasks_done()`: search `$wt_path/tasks.md` first, then `find $wt_path -maxdepth 3 -name tasks.md` excluding archive/node_modules
- [x] 3.2 Update tasks.md existence check in `cmd_start` to use same generic search
- [x] 3.3 Remove all `openspec/changes/` path references from wt-loop

## 4. Update GUI

- [x] 4.1 Update `start_ralph_loop_dialog()` in `gui/control_center/mixins/menus.py`: remove change_id parameter, pass only wt_path
- [x] 4.2 Update `wt-loop start` command construction in GUI: remove change_id from cmd list
- [x] 4.3 Update `focus_ralph_terminal()` in handlers.py: use worktree_name instead of change_id for title search
- [x] 4.4 Update test_19: change `openspec/changes/ralph-improve` paths to worktree root `tasks.md` and remove change_id from `start_ralph_loop_dialog` calls
- [x] 4.5 Update test_21: change `openspec/changes/$cid` paths to worktree root `tasks.md`, remove change_id from `start_ralph_loop_dialog` calls, update loop-state.json fixtures to use `worktree_name` instead of `change_id`
- [x] 4.6 Update test_22: replace `opsx:apply` skill name in activity test fixtures with a generic example (e.g. `wt:loop`)

## 5. Update MCP server

- [x] 5.1 Update `get_worktree_tasks()` in `mcp-server/wt_mcp_server.py`: replace `openspec/changes/*/tasks.md` glob with generic tasks.md search

## 6. Clean up documentation and metadata

- [x] 6.1 Update `README.md`: remove or rewrite "OpenSpec Integration" section
- [x] 6.2 Update `CONTRIBUTING.md`: remove openspec directory from file structure
- [x] 6.3 Update `set_tools/__init__.py`: remove "OpenSpec-driven" from description
- [x] 6.4 Update `docs/readme-guide.md`: remove OpenSpec references
- [x] 6.5 Update `bin/wt-control-init`: remove OpenSpec reference
- [x] 6.6 Update `CLAUDE.md`: remove `/opsx:apply` reference from auto-commit rule (change to generic skill reference)
- [x] 6.7 Update `.claude/commands/wt/status.md`: replace `opsx:apply`/`opsx:explore` examples with generic skill examples
- [x] 6.8 Update `docs/agent-messaging.md`: replace `opsx:apply` examples with generic skill examples
- [x] 6.9 Update `bin/wt-hook-skill` comments: replace `opsx:explore` example with generic example
- [x] 6.10 Update `bin/wt-skill-start` help: replace `opsx:explore` example with generic example

## 7. Ralph loop CLI tests (bash)

- [x] 7.1 Create `tests/bash/test_wt_loop.bats` (or equivalent test script): test CWD-based worktree detection — `wt-loop` inside a git worktree resolves path correctly
- [x] 7.2 Test `wt-loop` outside a git repo shows error
- [x] 7.3 Test `check_tasks_done()` finds `$wt_path/tasks.md` at worktree root
- [x] 7.4 Test `check_tasks_done()` fallback finds tasks.md in subdirectory (maxdepth 3)
- [x] 7.5 Test `check_tasks_done()` ignores archive/ directory
- [x] 7.6 Test `check_tasks_done()` correctly detects all-done (no `- [ ]` remaining)
- [x] 7.7 Test `check_tasks_done()` correctly detects not-done (`- [ ]` remaining)
- [x] 7.8 Test `init_loop_state()` writes `worktree_name` instead of `change_id`
- [x] 7.9 Test `build_prompt()` does not reference change-id
- [x] 7.10 Test `cmd_start` falls back to manual when no tasks.md exists

## 8. Ralph loop GUI tests (additional)

- [x] 8.1 Add test: `start_ralph_loop_dialog` builds command WITHOUT change_id positional arg (update existing test_21 test_dialog_accept_spawns_command)
- [x] 8.2 Add test: loop-state.json with `worktree_name` field is correctly read by `get_ralph_status`
- [x] 8.3 Add test: `focus_ralph_terminal` uses `worktree_name` for window title search instead of `change_id`
- [x] 8.4 Add test: tasks.md at worktree root is found by dialog's tasks detection (not just openspec path)
- [x] 8.5 Add test: tasks.md in arbitrary subdirectory (not openspec) is found by dialog's tasks detection
