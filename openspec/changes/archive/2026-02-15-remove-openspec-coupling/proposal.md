## Why

set-core has hardcoded OpenSpec dependencies throughout its CLI tools (`wt-new`, `wt-add`, `wt-loop`) and GUI. This couples the worktree management layer to a specific spec workflow tool. Since git worktrees already carry all files from the branch (including `openspec/` if initialized), the `openspec init` calls are redundant. The `wt-loop` takes a `change-id` parameter that maps to OpenSpec's concept, but it actually just identifies the worktree — and since the loop always runs inside a worktree (CWD), no identifier parameter is needed at all.

## What Changes

- **BREAKING** Remove `openspec init` calls from `wt-new` and `wt-add`
- **BREAKING** Remove `--no-openspec` flag from `wt-new` (and shell completions)
- **BREAKING** `wt-loop` becomes CWD-based: remove `change-id` positional parameter from all subcommands (`start`, `stop`, `status`, `history`, `monitor`, `run`)
- Remove `openspec/changes/$change_id/tasks.md` lookup from `wt-loop` — tasks.md search becomes simple: `$wt_path/tasks.md` or generic `find`
- Remove `detect_change_id_from_pwd()` function from `wt-loop` (no longer needed)
- Remove `find_existing_worktree()` / `resolve_project()` from `wt-loop start/run` (CWD is the worktree)
- Update `loop-state.json` schema: replace `change_id` with worktree path or display name
- Update GUI `start_ralph_loop_dialog` to stop passing `change_id`
- Update MCP server `get_worktree_tasks()` to use generic tasks.md search instead of openspec-specific paths
- Update terminal title / display from `Ralph: $change_id` to `Ralph: $(basename $wt_path)`
- Clean up documentation references (README, CONTRIBUTING, `set_tools/__init__.py`)
- Remove old `/openspec:*` skill references from `wt-new` help text

## Capabilities

### New Capabilities

_None — this is a simplification/removal change._

### Modified Capabilities

- `worktree-tools`: Remove openspec init from `wt-new` and `wt-add`, remove `--no-openspec` flag
- `ralph-loop`: Replace `change_id` parameter with CWD-based worktree detection, simplify tasks.md lookup

## Impact

- **bin/wt-new**: Remove openspec init block, `--no-openspec` flag, old help text
- **bin/wt-add**: Remove openspec init block
- **bin/wt-loop**: Major refactor — CWD-based, no change-id parameter
- **bin/wt-completions.bash**: Remove `--no-openspec`
- **bin/wt-completions.zsh**: Remove `--no-openspec`
- **bin/wt-control-init**: Remove openspec reference
- **gui/control_center/mixins/menus.py**: Remove change_id from ralph loop dialog
- **gui/control_center/mixins/handlers.py**: Update ralph terminal focus (title change)
- **mcp-server/wt_mcp_server.py**: Generic tasks.md search
- **tests/gui/test_19_*.py, test_21_*.py**: Update openspec paths in fixtures
- **README.md, CONTRIBUTING.md, set_tools/__init__.py, docs/readme-guide.md**: Remove/update openspec references
