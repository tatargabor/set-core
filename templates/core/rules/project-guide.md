# Project Guide — set-core Managed Project

This project was initialized with [set-core](https://github.com/ASetCoding/set-core), an orchestration framework for Claude Code. This guide explains the project structure so you can work effectively.

## File Ownership

| Pattern | Owner | On re-init |
|---------|-------|------------|
| `.claude/rules/set-*.md` | **set-core** — DO NOT modify | Overwritten |
| `.claude/rules/*.md` (no `set-` prefix) | **Project** — edit freely | Preserved |
| `.claude/commands/set/`, `.claude/commands/opsx/` | **set-core** | Overwritten |
| `.claude/skills/` | **set-core** | Overwritten |
| `CLAUDE.md` sections marked `<!-- set-core:managed -->` | **set-core** | Overwritten |
| `CLAUDE.md` sections without that marker | **Project** | Preserved |
| `set/orchestration/config.yaml` | **Project** | Additive merge only |
| `set/knowledge/` | **Project** | Never touched |
| `openspec/` | **Project** | Never touched |

**Rule of thumb:** `set-` prefix = hands off, everything else = yours.

## Adding Custom Rules

To add project-specific conventions (e.g., mobile patterns, domain rules):

1. Create `.claude/rules/<name>.md` — any name WITHOUT the `set-` prefix
2. These files are preserved across `set-project init` re-runs
3. They are loaded alongside set-core rules and respected by orchestration

Examples: `mobile-navigation.md`, `api-versioning.md`, `design-system.md`

## Project Knowledge

- `set/knowledge/project-knowledge.yaml` — cross-cutting files, feature scopes, verification rules, merge strategies
- `set/knowledge/memory-seed.yaml` — essential project memories auto-imported on init

Update these as the project evolves — they inform orchestration decisions.

## Using OpenSpec

This project has OpenSpec for structured changes. Available commands:

| Command | Purpose |
|---------|---------|
| `/opsx:explore` | Think through a problem before starting |
| `/opsx:new <name>` | Start a structured change (proposal → specs → design → tasks) |
| `/opsx:ff <name>` | Fast-forward — create all artifacts at once |
| `/opsx:apply` | Implement tasks from a change |
| `/opsx:verify` | Verify implementation before archiving |
| `/opsx:archive` | Finalize and close a completed change |

When writing changes, respect the existing `.claude/rules/` conventions — both set-core managed and project-owned.

## Extending Conventions

To add domain-specific patterns (mobile, fintech, ML, etc.):

1. **Create rules** in `.claude/rules/` describing the patterns
2. **Update knowledge** in `set/knowledge/project-knowledge.yaml` with cross-cutting files and feature scopes
3. These will be respected by orchestration alongside set-core rules

For larger extensions, use `/opsx:new` to plan the conventions as a structured change.

## Configuration

- `set/orchestration/config.yaml` — parallelism, quality gates, model selection, environment variables
- `.claude/project-type.yaml` — project type metadata (managed by `set-project init`)
