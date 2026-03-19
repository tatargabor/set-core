[< Back to README](../README.md)

# CLI Reference

Complete reference for all user-facing `wt-*` commands.

## Worktree Management

| Command | Description |
|---------|-------------|
| `set-new <change-id>` | Create new worktree + branch |
| `set-work <change-id>` | Open worktree in editor + Claude Code |
| `set-close <change-id>` | Close worktree (removes directory and branch) |
| `set-merge <change-id>` | Merge worktree branch back to main |
| `wt-add [path]` | Add existing repo or worktree to set-core |
| `set-list` | List all active worktrees |
| `set-status` | JSON status of all worktrees and agents |
| `wt-focus <change-id>` | Focus editor window for a worktree |

## Project Management

| Command | Description |
|---------|-------------|
| `set-project init` | Register project + deploy hooks, commands, and skills to `.claude/` (re-run to update) |
| `set-project list` | List registered projects |
| `set-project default <name>` | Set default project |

## Ralph Loop

| Command | Description |
|---------|-------------|
| `set-loop start [change-id]` | Start autonomous Claude Code loop |
| `set-loop stop [change-id]` | Stop running loop |
| `set-loop status [change-id]` | Show loop status |
| `set-loop list` | List all active loops |
| `set-loop history [change-id]` | Show iteration history |
| `set-loop monitor [change-id]` | Watch loop progress live |

## Orchestration

| Command | Description |
|---------|-------------|
| `set-orchestrate plan` | Generate change plan from spec/brief |
| `set-orchestrate plan --show` | Show existing plan |
| `set-orchestrate start` | Execute the plan (dispatch + monitor) |
| `set-orchestrate status` | Show current orchestration state |
| `set-orchestrate events [filters]` | Query event log (--type, --change, --since, --last, --json) |
| `set-orchestrate pause <name\|--all>` | Pause a change or all changes |
| `set-orchestrate resume <name\|--all>` | Resume a paused change or all |
| `set-orchestrate replan` | Re-plan from updated spec, preserving completed work |
| `set-orchestrate approve [--merge]` | Approve checkpoint / flush merge queue |

Options: `--spec <path>`, `--brief <path>`, `--phase <hint>`, `--max-parallel <N>`, `--time-limit <dur>`

## Sentinel

| Command | Description |
|---------|-------------|
| `set-sentinel` | Bash supervisor — monitors orchestrator, restarts on crash |

Agent mode: `/set:sentinel` (recommended) — AI agent with crash diagnosis, checkpoint auto-approve, and completion reports.

## Team & Sync

| Command | Description |
|---------|-------------|
| `set-control` | Launch Control Center GUI |
| `set-control-init` | Initialize set-control team sync branch |
| `set-control-sync` | Sync member status (pull/push/compact) |
| `set-control-chat send <to> <msg>` | Send encrypted message |
| `set-control-chat read` | Read received messages |

## Developer Memory

| Command | Description |
|---------|-------------|
| `set-memory health` | Check if shodh-memory is available |
| `set-memory remember --type TYPE` | Save a memory (reads content from stdin) |
| `set-memory recall "query" [--mode MODE] [--tags t1,t2]` | Semantic search with recall modes and tag filtering |
| `set-memory list [--type TYPE] [--limit N]` | List memories with optional filters (JSON) |
| `set-memory forget <id>` | Delete a single memory by ID |
| `set-memory forget --all --confirm` | Delete all memories (requires --confirm) |
| `set-memory forget --older-than <days>` | Delete memories older than N days |
| `set-memory forget --tags <t1,t2>` | Delete memories matching tags |
| `set-memory context [topic]` | Condensed summary by category |
| `set-memory brain` | 3-tier memory visualization |
| `set-memory get <id>` | Get a single memory by ID |
| `set-memory export [--output FILE]` | Export all memories to JSON (stdout or file) |
| `set-memory import FILE [--dry-run]` | Import memories from JSON (skip duplicates) |
| `set-memory sync` | Push + pull memories via git remote |
| `set-memory sync push` | Push memories to shared team branch |
| `set-memory sync pull` | Pull memories from shared team branch |
| `set-memory sync status` | Show sync status (local vs remote counts) |
| `set-memory proactive` | Generate proactive context for current session |
| `set-memory stats` | Show memory statistics (counts, types, noise ratio) |
| `set-memory cleanup` | Delete low-importance and noisy memories |
| `set-memory migrate` | Run pending memory storage migrations |
| `set-memory migrate --status` | Show migration history |
| `set-memory repair` | Repair index integrity |
| `set-memory audit [--threshold N] [--json]` | Report duplicate clusters and redundancy stats |
| `set-memory dedup [--threshold N] [--dry-run] [--interactive]` | Remove duplicate memories |
| `set-memory status [--json]` | Show memory config, health, and count |
| `set-memory projects` | List all projects with memory counts |
| `set-memory metrics [--since Nd] [--json]` | Injection quality report |
| `set-memory dashboard [--since Nd]` | Generate HTML dashboard |
| `set-memory rules add --topics "t1,t2" "content"` | Add a deterministic rule |
| `set-memory rules list` | List rules |
| `set-memory rules remove <id>` | Remove a rule |

## OpenSpec

| Command | Description |
|---------|-------------|
| `set-openspec status [--json]` | Show OpenSpec change status |
| `set-openspec init` | Initialize OpenSpec in the project |
| `set-openspec update` | Update OpenSpec skills to latest version |

## Design

| Command | Description |
|---------|-------------|
| `set-figma-fetch <docs-dir>` | Scan `docs-dir/**/*.md` for Figma URLs, fetch raw data + assemble `design-snapshot.md` |
| `set-figma-fetch <url> -o <dir>` | Fetch a single Figma file into a directory |
| `set-figma-fetch --force <docs-dir>` | Re-fetch even if snapshots already exist |
| `set-figma-fetch --reprocess <docs-dir>` | Re-assemble snapshots from existing raw data (no MCP calls) |

Output per Figma file goes to `<docs-dir>/figma-raw/<file-key>/` with raw MCP responses and per-file `design-snapshot.md`. A combined snapshot is written to `./design-snapshot.md` (project root) for pipeline compatibility.

Prerequisites: Figma MCP authenticated in Claude Code (`~/.claude/.credentials.json`), Python `mcp` SDK installed.

## Utilities

| Command | Description |
|---------|-------------|
| `set-config editor list` | List supported editors and availability |
| `set-config editor set <name>` | Set preferred editor |
| `set-usage` | Show Claude API token usage |
| `set-version` | Display version info (branch, commit, date) |
| `set-deploy-hooks <target-dir>` | Deploy Claude Code hooks to a directory |

<details>
<summary>Internal scripts (not for direct use)</summary>

These are called by other tools or by Claude Code hooks:

- `set-common.sh` — shared shell functions
- `set-hook-skill` — UserPromptSubmit hook (skill tracking)
- `set-hook-stop` — Stop hook (timestamp refresh + memory reminder)
- `set-hook-memory-recall` — automatic memory recall on prompts
- `set-hook-memory-save` — automatic memory save on session end
- `set-hook-memory-warmstart` — session start memory warmup
- `set-hook-memory-pretool` — pre-tool hot-topic recall
- `set-hook-memory-posttool` — post-tool error recall
- `set-skill-start` — register active skill for status display
- `set-control-gui` — GUI launcher (called by `set-control`)
- `wt-completions.bash` / `wt-completions.zsh` — shell completions
- `set-memory-hooks check/remove` — legacy inline hook management

</details>

---

*See also: [Getting Started](getting-started.md) · [Configuration](configuration.md) · [Worktree Management](worktrees.md)*
