[< Back to README](../README.md)

# Project Setup

`set-project init` is the single entry point for setting up set-core in any project. It registers the project, deploys all hooks, commands, skills, and agents to `.claude/`, and configures the MCP server. Re-run anytime to update.

## Quick Start

```bash
cd ~/my-project
set-project init                    # register + deploy everything
set-project init --dry-run          # preview changes without modifying files
set-project init --name custom-name # override auto-detected project name
```

## What Gets Deployed

| Deployed to | Content |
|-------------|---------|
| `.claude/hooks/` | 5-layer memory hooks, skill tracking, stop hooks |
| `.claude/commands/set/` | `/set:*` slash commands (new, work, list, merge, close, etc.) |
| `.claude/commands/opsx/` | `/opsx:*` slash commands (new, ff, apply, verify, archive, etc.) |
| `.claude/skills/` | Skill definitions (OpenSpec, wt management) |
| `.claude/agents/` | Specialized subagents (ralph-worker, code-reviewer) |
| `.claude/rules/` | Cross-cutting checklist template |
| `CLAUDE.md` | Persistent Memory + Auto-Commit sections (managed markers) |
| `.claude/.set-version` | Version tracking for migration |

## Version Tracking & Migration

Each `set-project init` stores the set-core version in `.claude/.set-version`. On subsequent runs, it compares versions and runs migrations:

- **Additive directive merge** — new `orchestration.yaml` directives appended as comments (never overwrites)
- **Template scaffolding** — deploys missing templates (e.g., `cross-cutting-checklist.md`)
- **Schema validation** — warns about unknown or deprecated directives

## Project Knowledge

Scaffold a `project-knowledge.yaml` for cross-cutting file awareness:

```bash
set-project init-knowledge
```

Scans the project for common patterns (i18n files, sidebar components, route definitions, database schemas) and generates a draft. The orchestrator uses this to make smarter decisions about file dependencies across changes.

See [project-knowledge.md](project-knowledge.md) for the full schema.

## wt/ Directory Convention

Projects using set-core can scaffold a `wt/` directory for organized orchestration artifacts:

```
wt/
├── specs/          # specification documents for orchestration
├── archive/        # archived completed changes
└── templates/      # project-specific templates
```

## Codebase Scraping (Planned)

`set-project scrape` will analyze a codebase and generate context for agents — extracting project structure, key patterns, API surfaces, and conventions into a format that memory and orchestration can use.

## Updating set-core in a Project

```bash
cd /path/to/set-core && git pull     # update set-core itself
cd ~/my-project && set-project init   # redeploy to project
```

Safe updates: existing config values are never overwritten, new directives are added as commented defaults.

## CLI Commands

| Command | Description |
|---------|-------------|
| `set-project init` | Register + deploy (re-run to update) |
| `set-project init --dry-run` | Preview changes |
| `set-project init-knowledge` | Scaffold project-knowledge.yaml |
| `set-project list` | List registered projects |
| `set-project default <name>` | Set default project |

## Bidirectional Flow

```
set-core (source)                     consumer project
   │                                      │
   ├── set-project init ──────────────────►│  deploy .claude/ files
   │                                      │
   │◄── run logs (bugs, design) ──────────┤  diagnostics after each run
   │◄── .claude/ diffs ──────────────────┤  sentinel/user improvements
   │◄── orchestration.yaml ──────────────┤  config evolution
   │                                      │
   ├── fix bugs, add features             │
   ├── set-project init ──────────────────►│  redeploy (with migration)
```

---

*See also: [Getting Started](getting-started.md) · [OpenSpec Workflow](openspec.md) · [Configuration](configuration.md) · [Orchestration](orchestration.md)*
