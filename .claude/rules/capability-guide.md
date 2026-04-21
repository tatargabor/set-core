# set-core Capability Guide

This project is **set-core** — an orchestration framework for Claude Code that manages parallel agent development via git worktrees, OpenSpec-driven planning, and automated quality gates.

## What do you want to do?

| Goal | Command | When |
|------|---------|------|
| Think through a problem | `/opsx:explore` | Before starting work, during design |
| Start a structured change | `/opsx:new <name>` | New feature, fix, or refactor |
| Quick change (all artifacts) | `/opsx:ff <name>` | When you know what to build |
| Continue a change | `/opsx:continue` | Next artifact in sequence |
| Implement tasks | `/opsx:apply` | Code the change |
| Verify implementation | `/opsx:verify` | Before archiving |
| Archive completed change | `/opsx:archive` | Finalize and close |
| Archive multiple changes | `/opsx:bulk-archive` | Batch cleanup |
| Sync specs to main | `/opsx:sync` | Update main specs without archiving |
| Run full orchestration | `/set:sentinel` | Autonomous multi-change execution |
| Decompose spec into plan | `/set:decompose` | Break spec into orchestration changes |
| Review a plan | `/set:plan-review` | Validate plan quality |
| Create worktree | `/set:new <id>` | Parallel development branch |
| Open worktree in editor | `/set:work <id>` | Start working in a worktree |
| List worktrees | `/set:list` | See active parallel work |
| Merge worktree | `/set:merge <id>` | Merge via integration gates |
| Close worktree | `/set:close <id>` | Clean up finished work |
| Check project health | `/set:audit` | Diagnose config/setup issues |
| Forensics on a finished run | `/set:forensics` | Post-run debugging / error triage |
| See agent activity | `/set:status` | What's everyone working on |
| Send message to agent | `/set:msg` | Cross-agent communication |
| Check inbox | `/set:inbox` | Read messages from other agents |
| Broadcast status | `/set:broadcast` | Tell team what you're doing |
| Remember something | `/set:memory` | Persistent memory operations |
| Quick todo | `/set:todo` | Capture idea for later |
| Push branch | `/set:push` | Push to remote |
| Start agent loop | `/set:loop` | Autonomous Ralph loop |
| Onboarding walkthrough | `/opsx:onboard` | First time? Start here |
| Quick help | `/set:help` | Feature reference |

## Typical Workflows

**Structured change (most common):**
```
/opsx:explore  →  /opsx:new  →  /opsx:apply  →  /opsx:verify  →  /opsx:archive
```

**Quick fix:**
```
/opsx:ff <name>  →  /opsx:apply  →  /opsx:verify  →  /opsx:archive
```

**Full autonomous orchestration:**
```
/set:sentinel --spec <path> --max-parallel 3
```

**Consumer project diagnostics:**
Read run logs → fix set-core bugs → `set-project init` to redeploy

## CLI Tools (bash)

| Tool | Purpose |
|------|---------|
| `set-new <id>` | Create worktree |
| `set-work <id>` | Open worktree in editor |
| `set-list` | List worktrees |
| `set-merge <id>` | Merge with integration gates |
| `set-close <id>` | Remove worktree |
| `set-orchestrate` | Core orchestration engine |
| `set-sentinel-finding` | Log sentinel findings |
| `set-sentinel-status` | Sentinel status registration |
| `set-project init` | Deploy set-core to a project |
| `set-memory` | Memory CLI (remember/recall/forget) |
| `set-status` | Show orchestration status |
| `set-audit scan` | Project health scan |
| `set-run-logs <run-id>` | Forensic analysis of a completed orchestration run |
| `openspec` | OpenSpec CLI (list/status/new) |

## MCP Tools (programmatic)

**Memory:** `remember`, `recall`, `proactive_context`, `brain`, `context_summary`, `forget`, `list_memories`, `memory_stats`

**Team:** `send_message`, `get_inbox`, `get_team_status`, `get_activity`

**Worktree:** `list_worktrees`, `get_worktree_tasks`, `get_ralph_status`

**Todo:** `add_todo`, `list_todos`, `complete_todo`

## Project Structure

| Path | What lives here |
|------|-----------------|
| `lib/set_orch/` | Core engine (Layer 1) — profile system, dispatcher, merger, gates |
| `modules/web/` | Web project type plugin (Layer 2) — Next.js, Playwright, Prisma |
| `modules/example/` | Reference plugin (Dungeon Builder) |
| `bin/` | CLI tools (set-new, set-work, etc.) |
| `.claude/rules/` | Rules for set-core development (NOT deployed to consumers) |
| `.claude/skills/` | Slash command implementations |
| `.claude/commands/` | Command definitions (set/, opsx/) |
| `templates/core/rules/` | Core rules deployed to consumer projects via set-project init |
| `openspec/specs/` | Capability specifications |
| `openspec/changes/` | Active changes |
| `docs/` | Documentation |
| `mcp-server/` | MCP server (FastMCP) |

## Key Architectural Rules

- **Layer 1 (lib/set_orch/)** is abstract — NEVER put project-specific logic here
- **Layer 2 (modules/)** implements project-type specifics (web patterns, framework detection)
- **All merges go through integration gates** — never `git merge` manually
- **Profile system is the extension point** — new behaviors go through ProjectType ABC
- **Consumer projects get set-core via `set-project init`** — templates/core/rules/ for universal rules, modules/*/templates/ for project-type rules
