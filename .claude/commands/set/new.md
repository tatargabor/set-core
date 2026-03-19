# Create New Worktree

Create a new worktree for the given change-id: $ARGUMENTS

```bash
set-new $ARGUMENTS
```

This creates:
- Worktree at `../<project>-wt-<change-id>/`
- Branch `change/<change-id>`

If the branch exists on remote, it will be checked out and tracked automatically.

Options:
- `-p, --project <name>` - Use specific project (default: auto-detect)
- `-b, --branch <name>` - Custom branch name (default: `change/<change-id>`)
- `--skip-fetch` - Skip git fetch (faster, but won't detect remote branches)
- `--new` - Force create new branch even if remote exists

ARGUMENTS: $ARGUMENTS
