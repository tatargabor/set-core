[< Back to README](../README.md)

# MCP Server

The MCP (Model Context Protocol) server exposes set-core functionality to Claude Code agents. Agents can check worktree status, read task lists, see team activity, and interact with the memory system — all without leaving the conversation.

## Setup

### Auto-configured

The installer (`install.sh`) and `set-project init` automatically register the MCP server with Claude Code.

### Manual setup

```bash
claude mcp add set-core --scope user -- python /path/to/set-core/mcp-server/wt_mcp_server.py
```

## Tools

### Worktree & Agent Tools

| Tool | Description |
|------|-------------|
| `list_worktrees` | List all worktrees across projects with status |
| `get_ralph_status` | Ralph loop status for a change (iteration, tasks) |
| `get_worktree_tasks` | Read tasks.md for a worktree |
| `get_team_status` | Team member activity across machines |
| `get_activity` | Agent activity for a change (skill, broadcast, timing) |
| `send_message` | Send directed message to another agent |
| `get_inbox` | Read incoming messages |

### Memory Tools

| Tool | Description |
|------|-------------|
| `remember` | Save a memory (content, type, tags) |
| `recall` | Semantic search across memories |
| `proactive_context` | Generate context for current topic |
| `forget` | Delete a memory by ID |
| `forget_by_tags` | Delete memories matching tags |
| `list_memories` | List memories with optional type filter |
| `get_memory` | Get a single memory by ID |
| `context_summary` | Condensed summary by category |
| `brain` | 3-tier memory visualization |
| `memory_stats` | Memory statistics (counts, types) |
| `memory_health` | Check if shodh-memory is available |
| `audit` | Report duplicate clusters |
| `cleanup` | Delete low-importance memories |
| `dedup` | Remove duplicate memories |
| `verify_index` | Check index integrity |
| `consolidation_report` | Memory consolidation analysis |
| `graph_stats` | Knowledge graph statistics |
| `recall_by_date` | Recall memories by date range |

### Sync Tools

| Tool | Description |
|------|-------------|
| `sync` | Push + pull memories via git |
| `sync_push` | Push memories to shared branch |
| `sync_pull` | Pull memories from shared branch |
| `sync_status` | Show sync state |
| `export_memories` | Export all memories to JSON |
| `import_memories` | Import memories from JSON file |

### Todo Tools

| Tool | Description |
|------|-------------|
| `add_todo` | Quick todo/idea capture |
| `list_todos` | List todos |
| `complete_todo` | Mark todo as complete |

## Resources

The server also exposes MCP resources for polling:

| Resource | URI | Description |
|----------|-----|-------------|
| Worktrees | `wt://worktrees` | All worktree data |
| Ralph status | `wt://ralph/status` | Ralph loop status |
| Team | `wt://team` | Team member activity |

## How Agents Use It

Agents in different worktrees can see each other through MCP tools:

```
# Agent in worktree A checks what agent B is doing:
→ get_activity("feature-b")
← { "skill": "opsx:apply", "broadcast": "Adding Google OAuth", "updated": "2 min ago" }

# Agent reads another worktree's task progress:
→ get_worktree_tasks("/path/to/worktree-b")
← "## Tasks\n- [x] 1.1 Add auth middleware\n- [ ] 1.2 Add user roles..."
```

## Status Line

The installer configures Claude Code's status line (`~/.claude/statusline.sh`) to show Ralph loop status:

```
folder (branch) | model | ctx 45% | Ralph: 3/10
```

---

*See also: [Team Sync & Messaging](team-sync.md) · [Developer Memory](developer-memory.md) · [Architecture](architecture.md)*
