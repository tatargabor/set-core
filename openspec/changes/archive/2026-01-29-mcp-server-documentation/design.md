## Context

The set-core system already has:
- **Control Center GUI** (PySide6) - worktree management, Ralph launch
- **wt skill** - action-based commands (wt-new, wt-close, wt-merge, wt-loop)
- **Ralph loop** - autonomous Claude iteration in separate terminal
- **CLI tools** - bash scripts under bin/

Current limitation: These components can't see each other. An agent running in Zed doesn't know if Ralph is running in another worktree.

## Goals / Non-Goals

**Goals:**
- MCP server providing READ-ONLY access to set-core state
- Cross-context visibility: any agent can query any worktree's state
- Status line integration: own worktree's Ralph status shown automatically
- Global availability: works in every project (`--scope user`)

**Non-Goals:**
- Command execution via MCP (remains in wt skill)
- GUI modifications (only cache file writing)
- Ralph loop changes (only state file format documentation)
- Zed extension development (not needed, MCP is sufficient)

## Decisions

### 1. FastMCP Python framework

**Decision:** FastMCP over raw `mcp` SDK

**Alternatives:**
- `mcp` SDK direct usage - more boilerplate
- Node.js `@modelcontextprotocol/sdk` - different language, less fitting

**Rationale:** FastMCP has a simple decorator-based API, tools can be defined quickly. set-core already uses Python (GUI), consistent.

### 2. Stdio transport

**Decision:** `--transport stdio` (not HTTP)

**Alternatives:**
- HTTP transport - more complex, server management
- SSE transport - deprecated

**Rationale:** Stdio is simple, Claude Code natively supports it, no port conflicts.

### 3. Read-only MCP, actions stay in skill

**Decision:** MCP only reads, doesn't execute commands

**Alternatives:**
- Actions in MCP too (wt_new, ralph_stop) - duplication with skill

**Rationale:** Clean separation:
- Skill = actions (wt-new, wt-close, wt-loop start)
- MCP = observation (get_ralph_status, list_worktrees)

No overlap, no confusion.

### 4. File-based communication

**Decision:** MCP reads JSON files, doesn't call CLI

```
Ralph writes:   <wt>/.claude/loop-state.json
GUI writes:     ~/.cache/set-core/team_status.json
MCP reads:      both
```

**Alternatives:**
- MCP calls CLI (wt-loop status) - slower, subprocess spawn
- Shared memory / socket - too complex

**Rationale:** File-based is simple, debuggable, no CLI dependency.

### 5. Worktree detection via pwd

**Decision:** Status line hook infers change-id from pwd

```bash
pwd: /home/user/code/project-wt-fix-bug
          ↓
change-id: fix-bug
```

**Alternatives:**
- Environment variable (WT_CHANGE_ID) - extra config
- Git branch parsing - more complex

**Rationale:** The worktree path convention (`<project>-wt-<change-id>`) already exists, easy to parse.

## Risks / Trade-offs

### Race condition on file read
**Risk:** Ralph writes, MCP reads simultaneously → partial JSON
**Mitigation:** On JSON parse error, retry or use previous value

### Status line polling overhead
**Risk:** Too frequent MCP calls may slow down the agent
**Mitigation:** Configurable polling interval, caching on MCP side

### loop-state.json format change
**Risk:** If Ralph changes the format, MCP breaks
**Mitigation:** Format documentation, version field introduction (v1)

### Global MCP config override
**Risk:** `--scope user` may override other MCP config
**Mitigation:** Check with mcp list before installation

## Open Questions

1. **Status line hook format** - What exactly does the Claude Code status line hook config look like?
2. **Polling interval** - How often should the status line refresh? (5s? 10s? 30s?)
3. **Team status cache** - When and how does the GUI write team_status.json?
4. **MCP resources vs tools** - Are resources (`wt://ralph/status`) useful, or are tools enough?
