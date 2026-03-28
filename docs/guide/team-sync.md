[< Back to Guides](README.md)

# Team Sync -- Multi-Agent Coordination

When running multiple agents across worktrees (or across machines), team sync enables them to communicate, share status, and avoid conflicts. This is essential during parallel orchestration where 3+ agents may be editing overlapping files.

## Agent Communication

### Sending Messages

```bash
set-msg <agent-id> "message"    # send a directed message
set-broadcast "working on auth"  # broadcast status to all agents
```

Messages are delivered to the agent's inbox. The recipient sees them on their next tool call (via the pre-tool memory hook) or by explicitly checking:

```bash
set-inbox                        # check incoming messages
```

### Checking Status

```bash
set-status                       # see what everyone is working on
```

![set-status output](../images/auto/cli/set-status.png)

This shows each active agent's current worktree, the skill or command running, and how long they have been active.

## MCP Tools

For programmatic access from within Claude Code sessions:

| Tool | Purpose |
|------|---------|
| `send_message` | Send a directed message to another agent |
| `get_inbox` | Read incoming messages |
| `get_team_status` | See all agent activity and current tasks |
| `get_activity` | Activity feed with timestamps |

## How It Works

Each agent periodically broadcasts its current activity (what skill is running, what file it is editing). This data flows through the shared memory layer, making it available to all agents in the same project. Agents use this to:

- **Avoid file conflicts** -- if agent A is editing `src/auth/login.ts`, agent B knows to defer changes to that file
- **Coordinate dependencies** -- agent B can wait for agent A to finish the auth module before starting the profile feature that depends on it
- **Share discoveries** -- if agent A finds a bug in the build system, it can message agent B to avoid the same issue

## During Orchestration

The orchestrator uses team sync automatically:

1. **Dispatch** -- when a change is dispatched to a worktree, the agent registers itself with team status
2. **Monitor** -- the sentinel reads team status to track which agents are active and what they are working on
3. **Conflict avoidance** -- the merge queue serializes merges, but team sync helps agents avoid editing the same cross-cutting files in parallel
4. **Stall investigation** -- when the watchdog detects a stall, it checks team status to understand the agent's last known activity

## Cross-Machine Sync

If you run agents on multiple machines (e.g., one developer machine and one cloud instance), team sync works through the memory layer's sync capability:

```bash
set-memory sync push    # push local state to remote
set-memory sync pull    # pull remote state to local
set-memory sync status  # check sync health and lag
```

This keeps memories, messages, and team status consistent across machines. The sync is eventual -- there may be a few seconds of lag, but it is sufficient for coordination at the pace agents operate.

## Practical Tips

- **Name your agents** -- use descriptive worktree names (`fix-login`, `add-cart-page`) so team status output is readable at a glance
- **Broadcast before long operations** -- if you are about to run a 10-minute build, broadcast so other agents know to wait
- **Check inbox after errors** -- another agent may have already discovered and messaged about the issue you are hitting
- **Use team status for debugging** -- when something seems stuck, `set-status` shows exactly what each agent is doing

---

*Next: [Memory](memory.md) | [Worktrees](worktrees.md) | [Dashboard](dashboard.md)*

<!-- specs: team-sync, agent-messaging, cross-context-visibility -->
