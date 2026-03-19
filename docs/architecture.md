[< Back to README](../README.md)

# Architecture

## Overview

set-core has four layers: **shell scripts** (`bin/set-*`) for worktree lifecycle, an **orchestration engine** (`set-orchestrate`) for autonomous multi-change execution, a **PySide6 GUI** for real-time monitoring, and an **MCP server** that connects Claude Code agents to the system. Everything is file-based — no daemon, no database, no external service.

```
┌─────────────────────────────────────────────────────────┐
│                   Control Center GUI                     │
│  PySide6 · always-on-top · light/dark/high-contrast     │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  Status: 5 worktrees | 2 running | 1 waiting       │ │
│  │  Usage:  4.2h/5h (85%) hourly  |  3.1d/7d daily    │ │
│  ├─────────────────────────────────────────────────────┤ │
│  │  Project  │ Branch      │ Status   │ Ctx%  │ Skill  │ │
│  │  my-app   │ add-auth    │ running  │ 45%   │ apply  │ │
│  │           │ fix-login   │ waiting  │ 80%   │        │ │
│  │  my-lib   │ refactor    │ idle     │       │        │ │
│  └─────────────────────────────────────────────────────┘ │
└────────────┬──────────────────────┬─────────────────────┘
             │                      │
             ▼                      ▼
  ┌────────────────────┐  ┌──────────────────┐
  │   CLI Tools (bash) │  │  MCP Server (py) │
  │   set-new/work/list │  │  list_worktrees  │
  │   set-loop (Ralph)  │  │  get_ralph_status│
  │   set-control-sync  │  │  get_team_status │
  └────────┬───────────┘  └────────┬─────────┘
           │                       │
           ▼                       ▼
  ┌──────────────────────────────────────────┐
  │  Orchestration Engine (set-orchestrate)   │
  │  spec → plan → dispatch → monitor       │
  │  parallel worktrees + merge queue        │
  ├──────────────────────────────────────────┤
  │  Git worktrees + set-control branch       │
  │  (file-based state, git for team sync)   │
  └──────────────────────────────────────────┘
```

## Technologies

| Component | Technology | Why |
|-----------|------------|-----|
| CLI tools | Bash | Zero dependencies, works everywhere, fast |
| Orchestration | Bash + Claude LLM | Spec decomposition, dependency DAG, parallel dispatch |
| GUI | Python + PySide6 (Qt) | Native look, always-on-top, system tray, cross-platform |
| MCP server | Python | Exposes worktree/agent data to Claude Code |
| State | JSON files + git | No database — `set-status` reads `/proc`, agent PIDs, git state |
| Team sync | Git branch (`set-control`) | No server — machines push/pull member status via git |
| Encryption | NaCl Box (libsodium) | End-to-end encrypted chat between team members |
| Memory | RocksDB (via shodh-memory) | Per-project semantic search with vector embeddings |

## Claude Code Agent Teams Integration

Claude Code's [Agent Teams](https://code.claude.com/docs/en/agent-teams) (experimental) let a lead session spawn teammate agents with shared task lists. This is complementary to set-core — Agent Teams work inside a single worktree, while set-core orchestrates across worktrees:

```
┌──────────────────────────────────────────────────────────┐
│  set-core (outer loop — git-level isolation)             │
│                                                          │
│  ┌──────────────────┐      ┌──────────────────┐         │
│  │ Worktree A        │      │ Worktree B        │         │
│  │ branch: add-auth  │      │ branch: fix-api   │         │
│  │                   │      │                   │         │
│  │  ┌─────────────┐ │      │  ┌─────────────┐ │         │
│  │  │ Agent Teams  │ │      │  │ Agent Teams  │ │         │
│  │  │  lead        │ │      │  │  lead        │ │         │
│  │  │  ├─ implement│ │      │  │  ├─ fix code │ │         │
│  │  │  ├─ test     │ │      │  │  └─ test     │ │         │
│  │  │  └─ docs     │ │      │  └─────────────┘ │         │
│  │  └─────────────┘ │      │                   │         │
│  └────────┬─────────┘      └────────┬─────────┘         │
│           │                         │                    │
│           └─── MCP + team sync ─────┘                    │
│                                                          │
│  Cross-machine: set-control git branch (no server)        │
└──────────────────────────────────────────────────────────┘
```

- **Agent Teams** = parallelism within a worktree (implement + test + docs at once)
- **set-core** = parallelism across worktrees (separate features in isolated branches)
- **Together** = nested parallelism with full git isolation

## Vision: Nested Agent Collaboration

The long-term direction is layered coordination — from local teammates inside a worktree, through cross-worktree MCP visibility, to cross-machine team sync:

```
Layer 3: Cross-machine (set-control git branch)
  ┌─────────────────┐          ┌─────────────────┐
  │  Linux machine   │◄────────►│  Mac machine     │
  │  3 worktrees     │  git sync │  2 worktrees     │
  └────────┬────────┘          └────────┬────────┘
           │                            │
Layer 2: Cross-worktree (MCP server)
  ┌────────┴────────────────────────────┴────────┐
  │  MCP: list_worktrees, get_team_status,       │
  │       get_worktree_tasks, get_ralph_status   │
  │  Agents see each other's progress & tasks    │
  └────────┬──────────┬──────────┬───────────────┘
           │          │          │
Layer 1: Within worktree (Agent Teams)
  ┌────────┴───┐ ┌────┴─────┐ ┌─┴──────────┐
  │ Lead agent │ │ Lead     │ │ Lead       │
  │ + 2 mates  │ │ + 1 mate │ │ solo       │
  │ (parallel) │ │          │ │ (Ralph)    │
  └────────────┘ └──────────┘ └────────────┘
```

## Planned Integrations

| Direction | Status | What it enables |
|-----------|--------|-----------------|
| **Custom subagents** (`.claude/agents/`) | Available now | Specialized `ralph-worker`, `code-reviewer` agents with persistent memory |
| **Additional hooks** (`SessionStart`, `PostToolUse`, `SessionEnd`) | Available now | Auto worktree detection, file tracking, idle status |
| **Async hooks** | Available now | Non-blocking activity tracking and team broadcasts |
| **Plugin packaging** | Available now | `plugin install set-core` — one-command setup |
| **SDK-based Ralph loops** | Available now | Structured output, crash recovery, session resume |
| **Persistent shared tasks** (`CLAUDE_CODE_TASK_LIST_ID`) | Available now | Cross-session task state for Ralph loops |
| **Agent Teams inner loop** | Experimental | Parallel subtasks within a single worktree |
| **MCP resource subscriptions** | When Claude Code supports it | Real-time push instead of polling |
| **GUI as Agent Teams monitor** | Future | Visualize `~/.claude/teams/` alongside worktrees |
| **GitHub Actions auto-review** | Available now | CI review of worktree branches before merge |

---

*See also: [Sentinel & Orchestration](sentinel.md) · [MCP Server](mcp-server.md) · [Plugins](plugins.md)*
