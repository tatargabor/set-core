# Close Worktree

Close/remove the worktree: $ARGUMENTS

```bash
set-close $ARGUMENTS
```

Interactive mode asks what to do with the branch:
1. Keep branch (can reopen later)
2. Delete local branch only
3. Delete local and remote branch

Non-interactive options:
- `--keep-branch` - Keep the branch
- `--force` - Force delete local branch
- `--delete-remote` - Delete remote branch too
