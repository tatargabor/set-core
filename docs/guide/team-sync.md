[< Back to Index](../INDEX.md)

# Team Sync — Multi-Agent Coordination

When running multiple agents across worktrees (or across machines), team sync enables them to communicate, share status, and avoid conflicts.

## Agent Communication

```bash
set-msg <agent-id> "message"    # send a directed message
set-inbox                        # check incoming messages
set-broadcast "working on auth"  # broadcast status to all agents
set-status                       # see what everyone is working on
```

## MCP Tools

| Tool | Purpose |
|------|---------|
| `send_message` | Send a message to another agent |
| `get_inbox` | Read incoming messages |
| `get_team_status` | See all agent activity |
| `get_activity` | Activity feed |

## How It Works

Each agent periodically broadcasts its current activity (what skill is running, what file it's editing). Other agents can query this to:

- **Avoid file conflicts** — know who's editing what
- **Coordinate dependencies** — wait for another agent to finish
- **Share discoveries** — pass information between worktrees

## Cross-Machine Sync

If you run agents on multiple machines, team sync works through the memory layer:

```bash
set-memory sync push    # push local state
set-memory sync pull    # pull remote state
set-memory sync status  # check sync health
```

---

*Next: [Memory](memory.md) · [Worktrees](worktrees.md) · [Dashboard](dashboard.md)*

<!-- specs: team-sync, agent-messaging, cross-context-visibility -->
