# Open Worktree for Work

Open the worktree in editor with Claude Code: $ARGUMENTS

```bash
set-work $ARGUMENTS
```

This opens the worktree in the configured editor and starts Claude Code in that context.
Creates the worktree if it doesn't exist (use `--no-create` to prevent this).

Options:
- `-e, --editor <name>` - Use specific editor (zed, vscode, cursor, windsurf, kitty, alacritty, etc.)
- `-p, --project <name>` - Use specific project (default: auto-detect)
- `--no-create` - Don't create worktree if it doesn't exist
- `--terminal` - Open in terminal mode instead of editor

ARGUMENTS: $ARGUMENTS
