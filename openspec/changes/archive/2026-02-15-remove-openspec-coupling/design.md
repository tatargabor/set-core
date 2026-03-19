## Context

set-core grew up alongside OpenSpec, and several CLI tools have hardcoded OpenSpec dependencies:
- `wt-new` and `wt-add` run `openspec init` on new worktrees — redundant because git worktrees inherit all files from the branch, including `openspec/` if already initialized
- `wt-loop` uses `change-id` as its primary identifier, mapped to OpenSpec change names, and searches `openspec/changes/$id/tasks.md` for done detection
- The GUI passes `change_id` to ralph loop functions even though it already knows the `wt_path`

The loop always runs inside a worktree (CWD), so no external identifier is needed.

## Goals / Non-Goals

**Goals:**
- Make set-core workflow-agnostic: users choose whether to use OpenSpec, plain tasks.md, or nothing
- Simplify wt-loop to be CWD-based (no identifier parameter needed)
- Remove all `openspec` CLI calls from shell scripts
- Simplify tasks.md lookup to worktree root

**Non-Goals:**
- Changing the `change/` branch naming convention in `wt-new` (this is a set-core convention, not OpenSpec-specific)
- Removing the `openspec/` directory or its contents from the repo
- Removing `.claude/skills/openspec-*` or `.claude/commands/opsx/` (these are user-facing workflow tools)
- Changing how the GUI table displays worktrees

## Decisions

### D1: wt-loop becomes fully CWD-based

All wt-loop subcommands derive the worktree path from CWD instead of requiring an identifier.

- `wt-loop start "task"` — CWD is the worktree
- `wt-loop stop` — CWD is the worktree
- `wt-loop status` — CWD is the worktree
- `wt-loop run` — internal, CWD set by spawning process
- `wt-loop list` — unchanged, scans all projects (the only global command)

Worktree path detection: `git rev-parse --show-toplevel` (works reliably in worktrees).

**Rationale**: The loop always operates on one worktree. The caller (CLI user, GUI, skill) already knows which worktree — either they're in it (CWD) or they set cwd when spawning the process. An abstract identifier adds indirection without value.

### D2: Remove detect_change_id_from_pwd() and find_existing_worktree() from wt-loop

These functions exist only to map an abstract ID back to a path. With CWD-based operation, they're unnecessary.

`find_existing_worktree()` in `wt-common.sh` stays (used by other tools), only the calls from `wt-loop` are removed.

### D3: tasks.md search simplification

Current search order (3 locations, openspec-specific):
1. `$wt_path/openspec/changes/$change_id/tasks.md`
2. `$wt_path/tasks.md`
3. `find $wt_path/openspec/changes -name tasks.md`

New search order (2 locations, generic):
1. `$wt_path/tasks.md` (worktree root — convention)
2. `find $wt_path -maxdepth 3 -name tasks.md` excluding `archive/` and `node_modules/` (fallback)

**Rationale**: If a user uses OpenSpec, their tasks.md lives in `openspec/changes/X/tasks.md` — the fallback find will discover it. If they put it at root, that's found first. The loop doesn't need to know about OpenSpec's directory structure.

### D4: loop-state.json schema change

Replace `change_id` field with `worktree_name` (basename of worktree path).

The `worktree_name` is used for display purposes only (terminal titles, status output, list command).

### D5: Terminal title format change

From: `Ralph: $change_id [iteration/max]`
To: `Ralph: $worktree_name [iteration/max]`

Where `worktree_name = basename "$wt_path"` (e.g., `project-wt-add-auth`).

### D6: Remove openspec init from wt-new and wt-add

Remove the `openspec init` block and `--no-openspec` flag entirely. Users who want OpenSpec run `openspec init` themselves.

### D7: MCP server tasks lookup

`get_worktree_tasks()` changes from `openspec/changes/*/tasks.md` glob to a generic `find` for `tasks.md` in the worktree (same logic as D3).

## Risks / Trade-offs

- **[Breaking CLI interface]** Users who call `wt-loop start <id> "task"` from scripts will break → Document in changelog, the positional arg is now just the task description
- **[tasks.md false positives]** Generic find might pick up unrelated tasks.md files → Mitigated by maxdepth 3 and excluding archive/node_modules
- **[Display name change]** Terminal titles show worktree dir name instead of change-id → These are typically similar (`project-wt-change-id` contains the change-id)
