# The wt-tools Ecosystem

## Overview

`wt-orchestrate` doesn't stand alone — it's part of a broader toolkit covering the entire AI-assisted development workflow. The `wt-tools` package includes CLI tools, hooks, a memory system, and project templates.

## Core Tools

### Worktree Lifecycle

These tools manage the full lifecycle of git worktrees — from creation to merge and cleanup. Each agent works in an isolated worktree on its own branch, without disturbing the main branch.

| Tool | Function |
|------|----------|
| `wt-new` | Create new worktree and branch, .claude/ initialization |
| `wt-list` | List active worktrees, status summary |
| `wt-status` | Detailed agent state: PID, iteration, tokens, model |
| `wt-merge` | Merge worktree to main, LLM conflict resolution |
| `wt-close` | Worktree cleanup (branch delete, directory removal) |
| `wt-focus` | Switch focus: terminal focus to selected worktree |
| `wt-add` | Add existing branch as worktree |

### Agent Execution

The Ralph loop is the iterative development cycle controlled by `wt-loop`. The agent writes code, runs tests, and decides on next steps in each iteration. The loop automatically handles context window limits, token budgets, and API rate limits.

| Tool | Function |
|------|----------|
| `wt-loop` | Ralph iterative loop: max-turns, token budget, model routing |
| `wt-work` | Interactive work session in a worktree |
| `wt-skill-start` | Skill-based session start in worktree |

### Orchestration and Supervision

The orchestration layer coordinates the entire pipeline — from specification processing to final merge. The sentinel is the supervisor that restarts the orchestrator on crash.

| Tool | Function |
|------|----------|
| `wt-orchestrate` | Full orchestration pipeline (the subject of this document) |
| `wt-sentinel` | Orchestrator supervisor: crash recovery, checkpoint handling |
| `wt-manual` | Manual orchestration intervention (debug, state editing) |
| `wt-e2e-report` | E2E test result aggregation and reporting |

### Memory and Context

The memory system ensures agents learn from previous sessions. Each project has its own memory database storing important decisions, lessons, and context. The hook system automatically injects relevant memories into the agent's context.

| Tool | Function |
|------|----------|
| `wt-memory` | Memory CLI: remember, recall, forget, search, sync |
| `wt-hook-memory` | Automatic memory injection (SessionStart, PostTool) |
| `wt-hook-memory-warmstart` | Session start: load relevant memories |
| `wt-hook-memory-recall` | Per-prompt topic-based memory recall |
| `wt-hook-memory-posttool` | Post-tool-use context augmentation |
| `wt-hook-memory-save` | Session-end memory save and extraction |

### Project Management

The `wt-project` system ensures new and existing projects can be set up with a single command — hooks, commands, skills installation, project registration. The `init` command is idempotent: re-running updates installed files without overwriting configuration.

| Tool | Function |
|------|----------|
| `wt-project` | Project initialization, hook deployment, registration |
| `wt-config` | Global and project-level configuration management |
| `wt-deploy-hooks` | Deploy Claude Code hooks to project |
| `wt-version` | Version display |
| `wt-usage` | Token usage statistics |

### Team Synchronization

Team sync enables communication between multiple developers (or agents) — messaging, activity sharing, memory synchronization. `wt-control` uses a git orphan branch as the communication channel.

| Tool | Function |
|------|----------|
| `wt-control` | Team sync: messaging, activity, coordination |
| `wt-control-init` | Team sync initialization (orphan branch) |
| `wt-control-sync` | Synchronize: push/pull messages and activity |
| `wt-control-chat` | Chat with other agents / developers |
| `wt-control-gui` | Graphical team dashboard |
| `wt-hook-activity` | Automatic activity sharing |

### OpenSpec and Quality

OpenSpec is the structured development workflow: from proposal through design and tasks to implementation. The audit and review tools ensure quality gates work not just in orchestration but in manual development too.

| Tool | Function |
|------|----------|
| `wt-openspec` | OpenSpec artifact management (proposal, design, tasks) |
| `wt-audit` | Code audit: security, quality, best practices |

## Project Templates

The `wt-project` system is template-based. Currently two templates are available, but the system is open to any technology stack:

### wt-project-base

The base template usable for any project. Includes:

- Claude Code hooks (memory, activity, skill dispatch)
- `/wt:*` commands (orchestrate, decompose, help)
- OpenSpec skills (fast-forward, apply, verify)
- Sentinel rules
- Default `.claude/` configuration

### wt-project-web (Next.js)

The web application template, extending `wt-project-base`. Includes:

- Next.js specific configurations
- Testing strategy (Jest + Playwright)
- Database handling (Prisma/Drizzle support)
- Pre-configured `smoke_command` and `e2e_command`
- Dev server management

### Other Directions

The template system is intentionally open. `wt-project-web` shows the Next.js direction, but any technology stack can be supported with a custom template:

- **wt-project-api** — REST/GraphQL API backends
- **wt-project-mobile** — React Native, Flutter applications
- **wt-project-python** — Python/FastAPI/Django projects
- **wt-project-scraper** — Data collection and processing projects

These templates would build on `wt-project-base` and add project-specific configuration, testing strategy, and build pipelines.

## Ecosystem Map

```
┌─────────────────────────────────────────────────────────┐
│                    wt-tools ecosystem                    │
├──────────────┬──────────────┬───────────────────────────┤
│  Worktree    │ Orchestration│  Memory & Context         │
│  lifecycle   │ & supervision│                           │
│              │              │                           │
│  wt-new      │ wt-orchestr. │  wt-memory               │
│  wt-list     │ wt-sentinel  │  wt-hook-memory-*        │
│  wt-status   │ wt-manual    │                           │
│  wt-merge    │ wt-e2e-rep.  │                           │
│  wt-close    │              │                           │
│  wt-loop     │              │                           │
├──────────────┼──────────────┼───────────────────────────┤
│  Project     │  Team Sync   │  OpenSpec & Quality       │
│  management  │              │                           │
│              │  wt-control  │  wt-openspec              │
│  wt-project  │  wt-ctrl-*   │  wt-audit                │
│  wt-config   │  wt-hook-act.│  /opsx:* skills          │
│  wt-deploy   │              │                           │
├──────────────┴──────────────┴───────────────────────────┤
│  Project templates                                      │
│  wt-project-base │ wt-project-web │ wt-project-...     │
└─────────────────────────────────────────────────────────┘
```

\begin{keypoint}
The ecosystem is modular: you don't have to use everything. The simplest entry point is wt-new + wt-loop (single agent, single worktree). Orchestration and the memory system can be enabled gradually, as needed.
\end{keypoint}
