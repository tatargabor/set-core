Read incoming messages directed to this agent.

**Usage**: `/set:inbox` or `/set:inbox --all`

**What to do**:

1. Find the project's `.set-control` worktree path:
   - Get the current project from `~/.config/set-core/projects.json`
   - The control worktree is at `<project_path>/.set-control`

2. Read messages using the CLI:
   ```bash
   set-control-chat --path <project_path> --json read
   ```

3. Parse the JSON output and filter messages:
   - Show messages addressed to the current member/worktree
   - By default, show only unread messages (newer than last read timestamp)
   - With `--all`, show all messages

4. Get the current member name:
   ```bash
   # Member name format: <git-user>@<hostname>
   git config user.name  # lowercase, spaces->hyphens
   hostname -s           # lowercase
   ```

5. Display messages in chronological order:
   ```
   INBOX (3 unread messages)

   [2026-02-08 10:30:15] tg@linux: Can you review the auth changes?
   [2026-02-08 10:45:22] peter@laptop: LGTM, merging now
   [2026-02-08 11:00:01] tg@linux: BUG: Start button doesn't work
     Steps: 1. Click start
     Expected: Game starts
     Actual: Nothing happens
   ```

6. If no messages: output "No unread messages"

7. After displaying, suggest replying: "Reply with `/set:msg <sender> <message>`"

ARGUMENTS: $ARGUMENTS
