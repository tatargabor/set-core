Show what all agents are currently working on.

**Usage**: `/wt:status`

**What to do**:

1. **Gather local activity** — Read `.wt/activity.json` from all worktrees across all projects:
   - Get projects from `~/.config/wt-tools/projects.json`
   - For each project, run `git worktree list --porcelain` to find all worktree paths
   - Read `.wt/activity.json` from each worktree (if it exists)
   - These are LOCAL agents (same machine), no "(remote)" tag

2. **Gather remote activity** — Read team cache from `~/.cache/wt-tools/team_status.json`:
   - Parse members array
   - Skip members whose name matches the local machine's member name (to avoid duplicates)
   - These are REMOTE agents, tag with "(remote)"

3. **Check for unread messages** — Read local outbox files from `.wt-control/chat/outbox/`:
   - Count messages addressed to the current member that are newer than the last read timestamp
   - If unread messages exist, show count and suggest `/wt:inbox`

4. **Display consolidated view**:
```
AGENT ACTIVITY

  /path/to/worktree-A (project-name)
    Skill: wt:loop add-oauth
    Broadcast: "Adding Google OAuth provider"
    Updated: 2 min ago

  /path/to/worktree-B (project-name) (stale)
    Skill: wt:status
    Updated: 15 min ago

  peter@laptop (remote)
    Skill: wt:loop fix-bug
    Broadcast: "Fixing payment checkout"
    Updated: 1 min ago

  3 unread messages — run /wt:inbox to read them
```

5. **Stale detection**: If `updated_at` is older than 5 minutes, show "(stale)" next to the entry

6. **Empty state**: If no activity files exist anywhere and no remote activity, output:
   "No active agents found"

7. **Relative timestamps**: Convert `updated_at` to relative format:
   - < 60s: "just now"
   - < 60m: "N min ago"
   - < 24h: "N hours ago"
   - else: the raw timestamp

**Use the MCP tool** `get_activity()` (from the wt-tools MCP server) for local activity if available. Otherwise fall back to direct file reads.
