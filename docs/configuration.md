[< Back to README](../README.md)

# Configuration

All wt-tools configuration files, their locations, and option reference.

## Config Files

| File | Location | Purpose |
|------|----------|---------|
| `gui-config.json` | `~/.config/wt-tools/` | GUI settings (opacity, theme, refresh) |
| `projects.json` | `~/.config/wt-tools/` | Project registry |
| `editor` | `~/.config/wt-tools/` | Preferred editor name |
| `orchestration.yaml` | `<project>/.claude/` | Orchestration settings |
| `rules.yaml` | `<project>/.claude/` | Deterministic memory rules |
| `project-knowledge.yaml` | `<project>/` | Cross-cutting file awareness |
| `.wt-version` | `<project>/.claude/` | Deployed wt-tools version |

## GUI Settings

`~/.config/wt-tools/gui-config.json`:

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
wt-config editor list           # list supported editors
wt-config editor set <name>     # set preferred editor
```

Supported editors: `zed` (primary), `vscode`, `cursor`, `windsurf`.

## Orchestration

`<project>/.claude/orchestration.yaml`:

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
plan_method: api               # api | agent
```

### Full Directive Reference

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
| `plan_method` | string | `api` | `api` (single LLM call) or `agent` (planning worktree with Ralph) |
| `context_pruning` | bool | `true` | Remove orchestrator commands from agent worktrees |
| `max_tokens_per_change` | int | `0` | Per-change token budget (0 = complexity defaults) |
| `watchdog_timeout` | int | `""` | Seconds before watchdog considers change stuck |
| `watchdog_loop_threshold` | int | `""` | Identical hashes before loop detection |
| `events_log` | string | `""` | Custom events JSONL path |
| `events_max_size` | int | `1048576` | Events log rotation threshold (bytes) |
| `post_merge_command` | string | `""` | Command after merge (e.g., Prisma generate) |

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

1. CLI flags (`--max-parallel`, `--time-limit`) — highest
2. Config file (`.claude/orchestration.yaml`)
3. In-document directives (`## Orchestrator Directives`)
4. Defaults — lowest

## Memory Rules

`<project>/.claude/rules.yaml` — deterministic rules matched by keyword against prompts:

```yaml
rules:
  - id: sql-customer-login
    topics: [customer, sql]
    content: |
      Use customer_ro / XYZ123 for customer table queries.
```

Manage via CLI:

```bash
wt-memory rules add --topics "customer,sql" "Use customer_ro for queries"
wt-memory rules list
wt-memory rules remove <id>
```

## Project Knowledge

`<project>/project-knowledge.yaml` — cross-cutting file awareness for smarter orchestration:

```bash
wt-project init-knowledge    # scaffold from project scan
```

See [project-knowledge.md](project-knowledge.md) for the full schema.

---

*See also: [Orchestration](orchestration.md) · [Developer Memory](developer-memory.md) · [CLI Reference](cli-reference.md)*
