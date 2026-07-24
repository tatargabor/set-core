# Project Guide — set-core Managed Project

This project was initialized with [set-core](https://github.com/ASetCoding/set-core), an orchestration framework for Claude Code. This guide explains the project structure so you can work effectively.

## File Ownership

**What decides is content, not the file name.** `set-project init` records the sha256 of
every file it writes, in `set/.deploy-manifest.json`. On the next run a file whose hash
still matches is treated as untouched and receives the update; a file that differs belongs
to this project and is left alone. The `set-` prefix marks *origin*, and keeps framework
names from colliding with yours — it is not what protects a file.

| Pattern | Origin | On re-init |
|---------|--------|------------|
| `.claude/rules/set-*.md`, `.claude/rules/<type>/set-*.md` | **set-core** | Updated **if unedited**; your edits are preserved |
| `.claude/rules/*.md` (no `set-` prefix) | **Project** (some seeded by set-core) | Seeded once, then never rewritten |
| `.claude/commands/set/`, `.claude/commands/opsx/` | **set-core** | Updated **if unedited** |
| `.claude/skills/` | **set-core** | Updated **if unedited** |
| Scaffold (`*.config.*`, `src/lib/prisma.ts`, i18n catalogues, hooks) | **Project** | Seeded once, then never rewritten |
| `CLAUDE.md` sections marked `<!-- set-core:managed -->` | **set-core** | Overwritten |
| `CLAUDE.md` sections without that marker | **Project** | Preserved |
| `set/orchestration/config.yaml` | **Project** | Additive merge only |
| `set/knowledge/` | **Project** | Never touched |
| `openspec/` | **Project** | Never touched |
| Anything set-core never deployed | **Project** | Never touched |

Two further guarantees:

- **A deletion is a decision.** Delete a file set-core deployed and it stays deleted — a
  tombstone is recorded, and the deletions already in your git history count too. To take
  the framework version back, remove the path from `tombstones` in
  `set/.deploy-manifest.json` and re-run the init.
- **Unknown provenance is never overwritten.** A file that existed before the ledger did is
  skipped, not guessed about.

Preview any run with `set-project init --dry-run`: it names every file it would write,
skip, or merge, and changes nothing.

## Adding Custom Rules

To add project-specific conventions (e.g., mobile patterns, domain rules):

1. Create `.claude/rules/<name>.md` — any name WITHOUT the `set-` prefix
2. Nothing set-core did not write is ever touched, so these survive every re-run
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
