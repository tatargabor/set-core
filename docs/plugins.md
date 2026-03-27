[< Back to README](../README.md)

# Plugins

> **Status: Experimental.** Plugin infrastructure is available but the ecosystem is just starting. The `set-plugin install` CLI is not yet implemented.

set-core is designed to be extensible. Plugins add new capabilities — custom skills, agents, hooks, or CLI commands — without modifying the core. Plugins live in separate repositories and are installed into projects independently.

## Concept

A plugin is a git repository containing any combination of:
- **Skills** (`.claude/skills/`) — Claude Code slash commands
- **Commands** (`.claude/commands/`) — Claude Code slash commands (user-facing)
- **Agents** (`.claude/agents/`) — specialized subagents
- **Hooks** — Claude Code hook scripts
- **CLI tools** (`bin/`) — shell commands

When installed, a plugin's files are deployed to the target project's `.claude/` directory, just like set-core core files.

## Installation

```bash
# Planned interface (not yet implemented):
set-plugin install <repo-url>

# Current approach: clone and manually deploy
git clone <plugin-repo> /path/to/plugin
cp -r /path/to/plugin/.claude/skills/* ~/my-project/.claude/skills/
```

## Plugin Registry

Known plugins. This list will grow as the ecosystem develops.

| Name | Repository | Description | Status |
|------|-----------|-------------|--------|
| *(no plugins registered yet)* | | | |

To list your plugin here, submit a PR adding it to this table.

## Creating a Plugin

A plugin repository should contain:

```
my-plugin/
├── README.md              # what it does, how to install
├── .claude/
│   ├── skills/            # skill definitions (SKILL.md files)
│   ├── commands/           # user-facing commands
│   └── agents/             # specialized agents
└── bin/                    # CLI tools (optional)
```

Follow the same conventions as set-core core:
- Skills have a `SKILL.md` with trigger conditions and instructions
- Commands have a matching `.md` file per command
- CLI tools are executable scripts with `--help` support

See [CONTRIBUTING.md](../CONTRIBUTING.md) for code style and conventions.

## Project Templates

Projects can provide their own template files that override or extend what the web module deploys. This is useful for project-specific conventions that don't belong in the generic web module.

### Setup

Create a `.claude/project-templates/` directory in your project root:

```
my-project/
├── .claude/
│   └── project-templates/        ← your overrides
│       ├── rules/
│       │   └── pci-compliance.md  ← project-specific rule
│       └── src/lib/prisma.ts      ← custom PrismaClient with audit logging
└── ...
```

### How it works

When `set-project init` runs, templates are applied in this order:

1. **Core rules** — universal rules from `templates/core/rules/`
2. **Web module templates** — Next.js boilerplate from `modules/web/templates/nextjs/`
3. **Project templates** — files from `.claude/project-templates/` override anything above

Files use the same path mapping as module templates:
- `rules/my-rule.md` → `.claude/rules/my-rule.md`
- `src/lib/prisma.ts` → `src/lib/prisma.ts` (project root)
- `framework-rules/web/custom.md` → `.claude/rules/web/set-custom.md`

### Example: custom Prisma client

The web module deploys a standard `src/lib/prisma.ts` with a globalThis singleton. If your project needs audit logging:

```typescript
// .claude/project-templates/src/lib/prisma.ts
import { PrismaClient } from "@prisma/client";

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };

export const prisma = globalForPrisma.prisma || new PrismaClient({
  log: [{ emit: "event", level: "query" }],
});

// Audit logging
prisma.$on("query", (e) => {
  console.log(`[DB] ${e.query} — ${e.duration}ms`);
});

if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = prisma;
```

On `set-project init`, this replaces the standard version. The output shows:
```
  [project-template] Overwritten: src/lib/prisma.ts
```

### When to use project templates vs module templates

| Use case | Where |
|----------|-------|
| Applies to ALL Next.js projects | Web module template |
| Applies to YOUR project only | `.claude/project-templates/` |
| E2E test scaffold conventions | `tests/e2e/scaffolds/<name>/templates/` |

---

*See also: [Getting Started](getting-started.md) · [Architecture](architecture.md) · [CLI Reference](cli-reference.md)*
