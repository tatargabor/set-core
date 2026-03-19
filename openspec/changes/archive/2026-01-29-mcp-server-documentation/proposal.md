## Why

The set-core ecosystem currently consists of isolated components (Control Center GUI, Ralph loop, CLI tools) that don't communicate with each other. AI agents (Claude Code in Zed, VS Code, terminal) can't see each other's work, Ralph loop status, or team activity.

By introducing an MCP (Model Context Protocol) server, all components can be connected, enabling:
- Coordination between agents
- Ralph loop monitoring from any editor
- Cross-context visibility (which the existing wt skill can't provide)

## What Changes

- **New MCP server** (`mcp-server/wt_mcp_server.py`): FastMCP-based server that exposes set-core STATE (read-only)
- **Ralph loop integration**: The MCP server directly reads worktree-level Ralph state files (`loop-state.json`)
- **Global availability**: The MCP server is available in every project (`--scope user`)
- **GUI-MCP connection**: The Control Center GUI writes team status cache that the MCP reads

**What does NOT change:**
- Zed integration: `wt-work` continues to open terminal with Claude
- wt skill: The existing action-based commands (wt-new, wt-close, wt-merge, wt-loop) remain unchanged
- Ralph loop operation: Runs in separate terminal, writes state file

## Skill vs MCP Delineation

```
┌─────────────────────────────────────────────────────────────┐
│              wt SKILL (actions - local context)              │
├─────────────────────────────────────────────────────────────┤
│  wt-new <id>       → create worktree                        │
│  wt-close <id>     → delete worktree                        │
│  wt-merge <id>     → branch merge                           │
│  wt-work <id>      → open editor (Zed + terminal)           │
│  wt-loop start/stop→ Ralph start/stop                       │
│                                                             │
│  ➜ COMMANDS that CHANGE something                           │
│  ➜ Used by the agent running in that worktree               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│           MCP SERVER (observation - cross-context)           │
├─────────────────────────────────────────────────────────────┤
│  list_worktrees()    → all worktree states                  │
│  get_ralph_status()  → Ralph loop state (any worktree)      │
│  get_team_status()   → team activity                        │
│  get_worktree_tasks()→ tasks.md content                     │
│                                                             │
│  ➜ READ-ONLY, observation only                              │
│  ➜ Accessible from other worktrees / editors                │
└─────────────────────────────────────────────────────────────┘
```

**Why are both needed?**
- The skill runs locally, where the agent works
- The MCP provides cross-context visibility
- Example: Zed agent (worktree A) → MCP → sees Ralph status (worktree B)

## Capabilities

### New Capabilities
- `mcp-server`: MCP server that exposes set-core state (read-only observation)
- `ralph-mcp-integration`: Querying Ralph loop state via MCP
- `cross-context-visibility`: Inter-agent visibility - who's working on what, in which worktree

### Modified Capabilities
- `ralph-loop`: loop-state.json format documentation (already worktree-level: `<wt-path>/.claude/loop-state.json`)
- `ralph-auto-detect`: If in a worktree, automatically detect change-id for every wt-loop command (start, stop, status, etc.)

## Impact

**File structure:**
```
~/.config/set-core/
  projects.json              ← MCP reads

<project>-wt-<change-id>/    ← worktree
  .claude/
    loop-state.json          ← Ralph state (MCP reads)
    ralph-loop.log           ← Ralph log

~/.cache/set-core/
  team_status.json           ← GUI writes, MCP reads

~/.claude.json               ← MCP server config (--scope user)
```

**Architecture:**

```
┌─────────────────────────────────────────────────────────────────┐
│                   MCP Server (set-core) - READ ONLY             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ list_       │  │ get_ralph_  │  │ get_team_   │              │
│  │ worktrees() │  │ status()    │  │ status()    │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                      │
│         ▼                ▼                ▼                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ projects    │  │ loop-state  │  │ team_status │              │
│  │ .json       │  │ .json (wt)  │  │ .json       │              │
│  └─────────────┘  └─────────────┘  └─────────────┘              │
└─────────────────────────────────────────────────────────────────┘
         ▲                 ▲                 ▲
         │    READS        │    READS        │    READS
         │                 │                 │
    ┌────┴────┐      ┌─────┴─────┐     ┌─────┴─────┐
    │ Claude  │      │  Ralph    │     │  Control  │
    │ Code    │      │  Loop     │     │  Center   │
    │ (any)   │      │ (WRITES)  │     │  (WRITES) │
    └─────────┘      └───────────┘     └───────────┘
```

**Zed workflow (unchanged):**
```
wt-work <change-id>
    ↓
Zed opens with worktree
    ↓
Terminal starts with Claude
    ↓
Claude agent sees other worktrees' Ralph status via MCP
```

## Status Line Integration

The Claude Code status line automatically shows the **own worktree's** Ralph state:

```
┌─────────────────────────────────────────────────────────────┐
│  Status Line (automatic, context-aware)                     │
├─────────────────────────────────────────────────────────────┤
│  Worktree: fix-bug                                          │
│  Ralph running in fix-bug → Status line: 🔄 Ralph: 3/10 (12m)│
│  Ralph NOT running        → Status line: (empty)            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  MCP query (manual, cross-context)                          │
├─────────────────────────────────────────────────────────────┤
│  Agent: get_ralph_status()              ← ALL worktrees     │
│  →  🔄 fix-bug: 3/10 (own)                                  │
│  →  ✅ feature-x: done                                       │
│  →  ⚠️ refactor-api: stuck                                   │
└─────────────────────────────────────────────────────────────┘
```

**Status line logic:**
1. Detects which worktree the agent is in (based on pwd)
2. MCP: `get_ralph_status(current_change_id)` - own only
3. If Ralph running → `🔄 Ralph: 3/10 (12m)`
4. If not → empty

**Configuration:**
```
~/.claude/hooks/
  statusLine.js    ← hook that calls MCP for own worktree
```

**Future possibilities:**
- Agents sending messages to each other via MCP
- Central task queue for multiple agents
- Automatic workload distribution
- GUI → MCP writes (sending commands) - but that's a separate change
