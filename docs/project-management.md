# Consumer Project Management

How to set up, maintain, and update wt-tools in a consumer project.

## Initial Setup

```bash
cd /path/to/your-project
wt-project init
```

This:
1. Registers the project in wt-tools registry
2. Deploys hooks, commands, skills, agents, and rules to `.claude/`
3. Registers the wt-tools MCP server
4. Adds `Persistent Memory` and `Auto-Commit After Apply` sections to `CLAUDE.md`
5. Writes `.claude/.wt-version` with the current wt-tools version

Use `--name <custom>` to override the project name (defaults to directory name).

## Version Tracking

Each `wt-project init` stores the wt-tools version (git short hash or tag) in `.claude/.wt-version`. On subsequent runs, wt-project compares the stored version against the current wt-tools version.

When a version change is detected, automatic migration runs:
- **Additive directive merge** — new `orchestration.yaml` directives are appended as comments (never overwrites existing values)
- **Template scaffolding** — deploys `cross-cutting-checklist.md` to `.claude/rules/` if missing
- **Schema validation** — warns about unknown or deprecated directives in `orchestration.yaml`

## Dry Run

Preview what `init` would change without modifying any files:

```bash
wt-project init --dry-run
```

## Project Knowledge

Scaffold a `project-knowledge.yaml` for cross-cutting file awareness:

```bash
wt-project init-knowledge
```

This scans the project for common patterns (i18n files, sidebar components, route definitions, database schemas) and generates a draft. See [project-knowledge.md](project-knowledge.md) for the full schema.

## Updating wt-tools

```bash
cd /path/to/wt-tools
git pull

# Re-deploy to all registered projects
wt-project list                    # see registered projects
cd /path/to/your-project && wt-project init   # update one project
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
wt-tools (source)                     consumer project
   │                                      │
   ├── wt-project init ──────────────────►│  deploy .claude/ files
   │                                      │
   │◄── run logs (bugs, design) ──────────┤  diagnostics after each run
   │◄── .claude/ diffs ──────────────────┤  sentinel/user improvements
   │◄── orchestration.yaml ──────────────┤  config evolution
   │                                      │
   ├── fix bugs, add features             │
   ├── wt-project init ──────────────────►│  redeploy (with migration)
```

After orchestration runs, check the run log for issues to report back to wt-tools development.
