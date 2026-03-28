> **Note:** This is the consumer project management reference. For getting started quickly, see [docs/guide/quick-start.md](guide/quick-start.md).

[< Back to README](../README.md)

# Consumer Project Management

How to set up, maintain, and update set-core in a consumer project.

## Initial Setup

```bash
cd /path/to/your-project
set-project init
```

This:
1. Registers the project in set-core registry
2. Deploys hooks, commands, skills, agents, and rules to `.claude/`
3. Registers the set-core MCP server
4. Adds `Persistent Memory` and `Auto-Commit After Apply` sections to `CLAUDE.md`
5. Writes `.claude/.set-version` with the current set-core version

Use `--name <custom>` to override the project name (defaults to directory name).

## Version Tracking

Each `set-project init` stores the set-core version (git short hash or tag) in `.claude/.set-version`. On subsequent runs, set-project compares the stored version against the current set-core version.

When a version change is detected, automatic migration runs:
- **Additive directive merge** — new `orchestration.yaml` directives are appended as comments (never overwrites existing values)
- **Core rules** — deploys `set-cross-cutting-checklist.md`, `set-design-bridge.md`, `set-sentinel-autonomy.md` to `.claude/rules/` from `templates/core/rules/`
- **Schema validation** — warns about unknown or deprecated directives in `orchestration.yaml`

## Dry Run

Preview what `init` would change without modifying any files:

```bash
set-project init --dry-run
```

## Project Knowledge

Scaffold a `project-knowledge.yaml` for cross-cutting file awareness:

```bash
set-project init-knowledge
```

This scans the project for common patterns (i18n files, sidebar components, route definitions, database schemas) and generates a draft. See [project-knowledge.md](project-knowledge.md) for the full schema.

## Updating set-core

```bash
cd /path/to/set-core
git pull

# Re-deploy to all registered projects
set-project list                    # see registered projects
cd /path/to/your-project && set-project init   # update one project
```

The migration system ensures updates are safe:
- Existing config values are never overwritten
- New directives are added as commented defaults
- Missing template files are scaffolded

## Orchestration Config

Create `.claude/orchestration.yaml` to configure orchestration runs:

```yaml
max_parallel: 2
default_model: opus
test_command: npm test
smoke_command: npm run test:smoke
smoke_timeout: 120
smoke_blocking: true
context_pruning: true
model_routing: off          # off | complexity
plan_approval: false        # require manual approval before dispatch
watchdog_timeout: 300       # seconds before watchdog considers a change stuck
max_tokens_per_change: 0    # 0 = use complexity defaults (S=500K, M=2M, L=5M, XL=10M)
```

See the [orchestration directive reference](orchestration.md#configuration) for all options.

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

After orchestration runs, check the run log for issues to report back to set-core development.

---

*See also: [Getting Started](getting-started.md) · [Configuration](configuration.md) · [Orchestration](orchestration.md)*
