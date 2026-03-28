[< Back to Guides](README.md)

# Persistent Memory

set-core includes a persistent memory system (shodh-memory) that gives agents cross-session recall — decisions, learnings, and context survive across conversations and are shared between agents.

## How It Works

Memory operates through **hooks** that fire automatically during Claude Code sessions:

| Hook | When | What |
|------|------|------|
| **Warmstart** | Session start | Loads relevant memories as context |
| **Pre-tool** | Before each tool call | Injects topic-based recall |
| **Post-tool** | After Read/Bash | Surfaces past experience for the file/command |
| **Save** | Session end | Extracts and saves new insights |

Agents don't need to explicitly save — the infrastructure handles it.

## CLI Commands

```bash
set-memory health          # check memory system status
set-memory stats           # memory statistics
set-memory recall "query"  # semantic search
set-memory list             # list all memories
set-memory forget <id>     # remove a memory
```

![Memory health](../images/auto/cli/set-memory-health.png)

![Memory stats](../images/auto/cli/set-memory-stats.png)

## Web Dashboard

The memory page shows health status, type breakdown, and retrieval statistics:

![Memory dashboard](../images/auto/web/page-memory.png)

## MCP Tools

The memory system is also available as MCP tools for programmatic access:

| Tool | Purpose |
|------|---------|
| `remember` | Save a memory with type and tags |
| `recall` | Semantic search |
| `brain` | 3-tier memory visualization |
| `context_summary` | Condensed summary by category |
| `proactive_context` | Topic-aware context injection |
| `forget` | Remove a memory |
| `list_memories` | List with filters |
| `memory_stats` | Health and metrics |

## Installation

```bash
pip install 'shodh-memory>=0.1.81'
set-memory health   # verify
```

Memory degrades gracefully — if not installed, all memory commands silently no-op. Agents work fine without it, they just don't have cross-session recall.

## Memory Types

Memories are categorized by type, which affects retrieval priority and display:

| Type | Purpose | Example |
|------|---------|---------|
| **Decision** | Architectural or design choices | "Chose eager merge policy for this project" |
| **Learning** | Patterns discovered during development | "vitest needs --passWithNoTests flag" |
| **Context** | Project state and configuration | "Project uses Prisma with PostgreSQL" |
| **Bug** | Known issues and their fixes | "Playwright flaky on CI without --retries=2" |
| **Feedback** | User preferences and corrections | "Never modify consumer project code" |

## Emphasis and Forgetting

Most memories are saved automatically by the session-end hook. For important insights you want to ensure are captured with high priority:

```bash
echo "Always use --project-type web for web projects" | set-memory remember --type Decision --tags source:user,init
```

To correct a wrong memory or suppress a false positive:

```bash
set-memory forget <memory-id>
```

## Cross-Agent Sharing

Memories are shared across all agents in the same project. When agent A discovers that a test requires a specific flag, agent B will receive that context in its next session through the warmstart hook. This eliminates redundant investigation across parallel worktrees.

## Key Insight

> Agents do not save memories voluntarily -- across 15+ sessions in benchmarks, zero voluntary saves were observed. The hook-driven infrastructure is essential for building useful cross-session recall.

---

*Next: [Dashboard](dashboard.md) | [Team Sync](team-sync.md) | [Worktrees](worktrees.md)*

<!-- specs: developer-memory-docs, ambient-memory, hook-driven-memory, memory-cli, mcp-memory-tools -->
