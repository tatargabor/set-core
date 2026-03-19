Send a directed message to another agent or team member.

**Usage**: `/set:msg <recipient> <message>`

**Input**: The first argument is the recipient (e.g., `tg@linux` or `tg@linux/gep2-linux` for a specific worktree). The rest is the message text.

**What to do**:

1. Parse the arguments: first word is recipient, rest is the message
2. Find the project's `.set-control` worktree path:
   - Get the current project from `~/.config/set-core/projects.json`
   - The control worktree is at `<project_path>/.set-control`
3. Run the send command with `--no-push` (message will be delivered on next sync cycle):
   ```bash
   set-control-chat --path <project_path> --no-push send <recipient> "<message>"
   ```
4. Report success or failure

**Important**:
- Uses `--no-push` so the message is queued locally and delivered on the next sync cycle (~15 seconds)
- This adds ZERO additional git operations — the existing sync cycle picks up outbox changes
- For multiline messages, the agent can write to a temp file and pipe it:
  ```bash
  echo "<message>" | set-control-chat --path <project_path> --no-push send <recipient> -
  ```
- If recipient has multiple worktrees, specify `<member>/<change_id>` to target a specific one
- If recipient is not found, the command will list available members

ARGUMENTS: $ARGUMENTS
