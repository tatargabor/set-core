## Why

`wt-close` currently has a `--force` flag that bypasses all safety checks — skipping uncommitted change detection and silently deleting branches with unpushed commits. This leads to silent code loss, especially when used by agents (wt-loop) or the GUI, which always pass `--force` to avoid interactive prompts. There is also no check for unpushed commits at all, so even interactive use can result in lost work if the user chooses to delete a branch that was never pushed.

## What Changes

- **BREAKING**: Remove `--force` flag from `wt-close` — no way to skip safety checks
- Add unpushed/unmerged commit detection before branch deletion — warn if branch has commits not in master and not on remote
- Add `--keep-branch` flag for non-interactive safe mode (agent/GUI use)
- Add `--delete-branch` flag for non-interactive branch deletion — only succeeds if branch is fully merged or pushed to remote
- Uncommitted changes check always blocks (no bypass)
- Interactive branch deletion shows explicit warning with commit count when commits would be lost
- Update GUI to use `--keep-branch` instead of `--force`

## Capabilities

### New Capabilities

_(none)_

### Modified Capabilities

- `worktree-tools`: Worktree Removal requirement changes — remove `--force` scenario, add safety checks for unpushed commits, add `--keep-branch` and `--delete-branch` flags

## Impact

- `bin/wt-close`: Main script rewrite of flag handling and safety checks
- `gui/control_center/mixins/handlers.py`: Change `--force` to `--keep-branch`
- `bin/wt-completions.bash`: Update completions (remove --force, add new flags)
- `bin/wt-completions.zsh`: Update completions (remove --force, add new flags)
- Any documentation referencing `--force` in wt-close
