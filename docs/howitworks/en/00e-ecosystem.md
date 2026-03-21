# The set-core Ecosystem

## Overview

`set-orchestrate` doesn't stand alone — it's part of a broader toolkit covering the entire AI-assisted development workflow. The `set-core` package includes CLI tools, hooks, a memory system, and project templates.

## Core Tools

### Worktree Lifecycle

These tools manage the full lifecycle of git worktrees — from creation to merge and cleanup. Each agent works in an isolated worktree on its own branch, without disturbing the main branch.

| Tool | Function |
|------|----------|
| `set-new` | Create new worktree and branch, .claude/ initialization |
| `set-list` | List active worktrees, status summary |
| `set-status` | Detailed agent state: PID, iteration, tokens, model |
| `set-merge` | Merge worktree to main, LLM conflict resolution |
| `set-close` | Worktree cleanup (branch delete, directory removal) |
| `set-focus` | Switch focus: terminal focus to selected worktree |
| `set-add` | Add existing branch as worktree |

### Agent Execution

The Ralph loop is the iterative development cycle controlled by `set-loop`. The agent writes code, runs tests, and decides on next steps in each iteration. The loop automatically handles context window limits, token budgets, and API rate limits.

| Tool | Function |
|------|----------|
| `set-loop` | Ralph iterative loop: max-turns, token budget, model routing |
| `set-work` | Interactive work session in a worktree |
| `set-skill-start` | Skill-based session start in worktree |

### Orchestration and Supervision

The orchestration layer coordinates the entire pipeline — from specification processing to final merge. The sentinel is the supervisor that restarts the orchestrator on crash.

| Tool | Function |
|------|----------|
| `set-orchestrate` | Full orchestration pipeline (the subject of this document) |
| `set-sentinel` | Orchestrator supervisor: crash recovery, checkpoint handling |
| `set-manual` | Manual orchestration intervention (debug, state editing) |
| `set-e2e-report` | E2E test result aggregation and reporting |

### Memory and Context

The memory system ensures agents learn from previous sessions. Each project has its own memory database storing important decisions, lessons, and context. The hook system automatically injects relevant memories into the agent's context.

| Tool | Function |
|------|----------|
| `set-memory` | Memory CLI: remember, recall, forget, search, sync |
| `set-hook-memory` | Automatic memory injection (SessionStart, PostTool) |
| `set-hook-memory-warmstart` | Session start: load relevant memories |
| `set-hook-memory-recall` | Per-prompt topic-based memory recall |
| `set-hook-memory-posttool` | Post-tool-use context augmentation |
| `set-hook-memory-save` | Session-end memory save and extraction |

### Project Management

The `set-project` system ensures new and existing projects can be set up with a single command — hooks, commands, skills installation, project registration. The `init` command is idempotent: re-running updates installed files without overwriting configuration.

| Tool | Function |
|------|----------|
| `set-project` | Project initialization, hook deployment, registration |
| `set-config` | Global and project-level configuration management |
| `set-deploy-hooks` | Deploy Claude Code hooks to project |
| `set-version` | Version display |
| `set-usage` | Token usage statistics |

### Team Synchronization

Team sync enables communication between multiple developers (or agents) — messaging, activity sharing, memory synchronization. `set-control` uses a git orphan branch as the communication channel.

| Tool | Function |
|------|----------|
| `set-control` | Team sync: messaging, activity, coordination |
| `set-control-init` | Team sync initialization (orphan branch) |
| `set-control-sync` | Synchronize: push/pull messages and activity |
| `set-control-chat` | Chat with other agents / developers |
| `set-control-gui` | Graphical team dashboard |
| `set-hook-activity` | Automatic activity sharing |

### OpenSpec and Quality

OpenSpec is the structured development workflow: from proposal through design and tasks to implementation. The audit and review tools ensure quality gates work not just in orchestration but in manual development too.

| Tool | Function |
|------|----------|
| `set-openspec` | OpenSpec artifact management (proposal, design, tasks) |
| `set-audit` | Code audit: security, quality, best practices |

## Project Types and Modules

The `set-project` system is modular. The base profile (`CoreProfile`) is integrated into set-core's core, while project-specific types live in the `modules/` directory or as external plugins.

### CoreProfile (set-core built-in)

The base profile usable for any project. Lives in `lib/set_orch/profile_loader.py` (`CoreProfile`) and `lib/set_orch/profile_types.py` (ABC). Includes:

- Claude Code hooks (memory, activity, skill dispatch)
- `/set:*` commands (orchestrate, decompose, help)
- OpenSpec skills (fast-forward, apply, verify)
- Sentinel rules
- Default `.claude/` configuration

### Web module — `modules/web/` (Next.js)

The web application module, extending `CoreProfile` (`WebProjectType`). Located at `modules/web/set_project_web/`. Includes:

- Next.js specific configurations
- Testing strategy (Jest + Playwright)
- Database handling (Prisma/Drizzle support)
- Pre-configured `smoke_command` and `e2e_command`
- Dev server management

### Example module — `modules/example/`

The Dungeon Builder example project, demonstrating how to create a custom project type plugin.

### External Plugins

The module system is intentionally open. Beyond built-in modules, any technology stack can be supported via external plugins (entry_points):

- **set-project-api** — REST/GraphQL API backends
- **set-project-mobile** — React Native, Flutter applications
- **set-project-python** — Python/FastAPI/Django projects
- **set-project-scraper** — Data collection and processing projects

These plugins would build on `CoreProfile` and add project-specific configuration, testing strategy, and build pipelines. Profile resolution order: entry_points → direct import → built-in modules/ → NullProfile.

## Ecosystem Map

```
┌─────────────────────────────────────────────────────────┐
│                    set-core ecosystem                    │
├──────────────┬──────────────┬───────────────────────────┤
│  Worktree    │ Orchestration│  Memory & Context         │
│  lifecycle   │ & supervision│                           │
│              │              │                           │
│  set-new      │ set-orchestr. │  set-memory               │
│  set-list     │ set-sentinel  │  set-hook-memory-*        │
│  set-status   │ set-manual    │                           │
│  set-merge    │ set-e2e-rep.  │                           │
│  set-close    │              │                           │
│  set-loop     │              │                           │
├──────────────┼──────────────┼───────────────────────────┤
│  Project     │  Team Sync   │  OpenSpec & Quality       │
│  management  │              │                           │
│              │  set-control  │  set-openspec              │
│  set-project  │  set-ctrl-*   │  set-audit                │
│  set-config   │  set-hook-act.│  /opsx:* skills          │
│  set-deploy   │              │                           │
├──────────────┴──────────────┴───────────────────────────┤
│  Project types (monorepo)                               │
│  CoreProfile (built-in) │ modules/web/ │ modules/example/  │
└─────────────────────────────────────────────────────────┘
```

\begin{keypoint}
The ecosystem is modular: you don't have to use everything. The simplest entry point is set-new + set-loop (single agent, single worktree). Orchestration and the memory system can be enabled gradually, as needed.
\end{keypoint}
