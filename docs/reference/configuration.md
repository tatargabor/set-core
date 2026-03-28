[< Back to INDEX](../INDEX.md)

# Configuration

All set-core configuration files, their locations, and option reference.

## Config File Overview

| File | Location | Purpose |
|------|----------|---------|
| `orchestration.yaml` | `<project>/.claude/` | Orchestration engine settings |
| `project-type.yaml` | `<project>/.claude/` | Project type and template (web, example) |
| `gui-config.json` | `~/.config/set-core/` | GUI appearance and refresh |
| `projects.json` | `~/.config/set-core/` | Project registry |
| `editor` | `~/.config/set-core/` | Preferred editor name |
| `rules.yaml` | `<project>/.claude/` | Deterministic memory rules |
| `project-knowledge.yaml` | `<project>/` | Cross-cutting file awareness |
| `.set-version` | `<project>/.claude/` | Deployed set-core version |
| `.env` | `<project>/` | Environment variables (API keys, ports) |
| `CLAUDE.md` | `<project>/` | Project instructions for Claude Code |

## orchestration.yaml

Primary configuration for the orchestration engine. Lives at `<project>/.claude/orchestration.yaml`.

```yaml
max_parallel: 2
default_model: opus
merge_policy: checkpoint    # eager | checkpoint | manual
checkpoint_every: 3
test_command: npm test
smoke_command: pnpm test:smoke
smoke_timeout: 120
smoke_blocking: true
post_merge_command: pnpm db:generate
auto_replan: true
pause_on_exit: false
context_pruning: true
model_routing: off          # off | complexity
plan_approval: false
plan_method: api            # api | agent
```

### Directive Reference

| Directive | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_parallel` | int | `2` | Max concurrent changes |
| `default_model` | string | `opus` | Default LLM model |
| `time_limit` | duration | `5h` | Stop after duration (`2h`, `4h30m`, `none`) |
| `checkpoint_interval` | int | `5` | Merge-checkpoint every N changes |
| `test_command` | string | `""` | Test command before merge |
| `build_command` | string | `""` | Build command before merge |
| `smoke_command` | string | `""` | Post-merge smoke test |
| `smoke_timeout` | int | `120` | Smoke test timeout (seconds) |
| `smoke_blocking` | bool | `true` | Smoke failure blocks pipeline |
| `review_model` | string | `""` | Model for code review gate |
| `model_routing` | string | `off` | `off` or `complexity` |
| `plan_approval` | bool | `false` | Require approval after plan |
| `plan_method` | string | `api` | `api` (single LLM call) or `agent` (planning worktree) |
| `context_pruning` | bool | `true` | Remove orchestrator commands from agent worktrees |
| `max_tokens_per_change` | int | `0` | Per-change token budget (0 = complexity defaults) |
| `watchdog_timeout` | int | `""` | Seconds before watchdog considers change stuck |
| `watchdog_loop_threshold` | int | `""` | Identical hashes before loop detection |
| `events_log` | string | `""` | Custom events JSONL path |
| `events_max_size` | int | `1048576` | Events log rotation threshold (bytes) |
| `post_merge_command` | string | `""` | Command after merge (e.g., `pnpm db:generate`) |

### Hooks

| Directive | Description |
|-----------|-------------|
| `hook_pre_dispatch` | Before dispatching a change (non-zero blocks) |
| `hook_post_verify` | After verification passes (non-zero blocks merge) |
| `hook_pre_merge` | Before merge (non-zero blocks) |
| `hook_post_merge` | After successful merge (non-blocking) |
| `hook_on_fail` | When change transitions to `failed` |

Hook scripts receive `(change_name, status, worktree_path)` as arguments.

### Setting Precedence

1. **CLI flags** (`--max-parallel`, `--time-limit`) — highest priority
2. **Config file** (`.claude/orchestration.yaml`)
3. **In-document directives** (`## Orchestrator Directives` in spec)
4. **Defaults** — lowest priority

## project-type.yaml

Identifies the project type so the correct profile loads. Created by `set-project init`.

```yaml
project_type: web
template: nextjs
```

Without this file, `NullProfile` loads and integration gates silently skip (no build/test/e2e detection).

## gui-config.json

GUI appearance settings at `~/.config/set-core/gui-config.json`:

```json
{
  "control_center": {
    "opacity_default": 0.5,
    "opacity_hover": 1.0,
    "window_width": 500,
    "refresh_interval_ms": 2000,
    "blink_interval_ms": 500,
    "color_profile": "light"
  }
}
```

| Setting | Default | Description |
|---------|---------|-------------|
| `opacity_default` | `0.5` | Window opacity when not hovered |
| `opacity_hover` | `1.0` | Window opacity on hover |
| `window_width` | `500` | Window width in pixels |
| `refresh_interval_ms` | `2000` | Status refresh interval |
| `blink_interval_ms` | `500` | Blink interval for waiting agents |
| `color_profile` | `"light"` | Color theme: `light`, `dark`, `high_contrast` |

## Editor Configuration

```bash
set-config editor list           # list supported editors
set-config editor set <name>     # set preferred editor
```

Supported editors: `zed` (primary), `vscode`, `cursor`, `windsurf`.

![set-config editor list](../images/auto/cli/set-config-editor-list.png)

## Environment Variables

Common `.env` variables used by set-core and consumer projects:

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Claude API key for orchestration |
| `E2E_PROJECT` | Project name for E2E tests |
| `SET_CORE_DEBUG` | Enable debug logging |
| `CLAUDE_MODEL` | Override default model |

## Memory Rules

`<project>/.claude/rules.yaml` — deterministic rules matched by keyword:

```yaml
rules:
  - id: sql-customer-login
    topics: [customer, sql]
    content: |
      Use customer_ro / XYZ123 for customer table queries.
```

Manage via CLI:

```bash
set-memory rules add --topics "customer,sql" "Use customer_ro for queries"
set-memory rules list
set-memory rules remove <id>
```

## CLAUDE.md

Project-level instructions read by Claude Code on every session. Typical sections:

- **Persistent Memory** — automatic memory injection setup
- **Help and Documentation** — where to find skill/CLI docs
- **Getting Started** — install, dev, test commands
- **E2E Run Setup** — how to scaffold and start E2E runs

This file is maintained manually. `set-project init` does not overwrite it.

---

<!-- Spec cross-references:
  - openspec/specs/orchestration-engine.md (orchestration.yaml directives)
  - openspec/specs/developer-memory.md (rules.yaml)
  - openspec/specs/profile-system.md (project-type.yaml, profile chain)
-->

*See also: [CLI Reference](cli.md) · [Architecture](architecture.md) · [Plugins](plugins.md)*

<!-- specs: orchestration-config, gate-profiles, web-template-configs -->
