[< Back to README](../README.md)

# CLI Reference

Complete reference for all user-facing `wt-*` commands.

## Worktree Management

| Command | Description |
|---------|-------------|
| `wt-new <change-id>` | Create new worktree + branch |
| `wt-work <change-id>` | Open worktree in editor + Claude Code |
| `wt-close <change-id>` | Close worktree (removes directory and branch) |
| `wt-merge <change-id>` | Merge worktree branch back to main |
| `wt-add [path]` | Add existing repo or worktree to wt-tools |
| `wt-list` | List all active worktrees |
| `wt-status` | JSON status of all worktrees and agents |
| `wt-focus <change-id>` | Focus editor window for a worktree |

## Project Management

| Command | Description |
|---------|-------------|
| `wt-project init` | Register project + deploy hooks, commands, and skills to `.claude/` (re-run to update) |
| `wt-project list` | List registered projects |
| `wt-project default <name>` | Set default project |

## Ralph Loop

| Command | Description |
|---------|-------------|
| `wt-loop start [change-id]` | Start autonomous Claude Code loop |
| `wt-loop stop [change-id]` | Stop running loop |
| `wt-loop status [change-id]` | Show loop status |
| `wt-loop list` | List all active loops |
| `wt-loop history [change-id]` | Show iteration history |
| `wt-loop monitor [change-id]` | Watch loop progress live |

## Orchestration

| Command | Description |
|---------|-------------|
| `wt-orchestrate plan` | Generate change plan from spec/brief |
| `wt-orchestrate plan --show` | Show existing plan |
| `wt-orchestrate start` | Execute the plan (dispatch + monitor) |
| `wt-orchestrate status` | Show current orchestration state |
| `wt-orchestrate events [filters]` | Query event log (--type, --change, --since, --last, --json) |
| `wt-orchestrate pause <name\|--all>` | Pause a change or all changes |
| `wt-orchestrate resume <name\|--all>` | Resume a paused change or all |
| `wt-orchestrate replan` | Re-plan from updated spec, preserving completed work |
| `wt-orchestrate approve [--merge]` | Approve checkpoint / flush merge queue |

Options: `--spec <path>`, `--brief <path>`, `--phase <hint>`, `--max-parallel <N>`, `--time-limit <dur>`

## Sentinel

| Command | Description |
|---------|-------------|
| `wt-sentinel` | Bash supervisor — monitors orchestrator, restarts on crash |

Agent mode: `/wt:sentinel` (recommended) — AI agent with crash diagnosis, checkpoint auto-approve, and completion reports.

## Team & Sync

| Command | Description |
|---------|-------------|
| `wt-control` | Launch Control Center GUI |
| `wt-control-init` | Initialize wt-control team sync branch |
| `wt-control-sync` | Sync member status (pull/push/compact) |
| `wt-control-chat send <to> <msg>` | Send encrypted message |
| `wt-control-chat read` | Read received messages |

## Developer Memory

| Command | Description |
|---------|-------------|
| `wt-memory health` | Check if shodh-memory is available |
| `wt-memory remember --type TYPE` | Save a memory (reads content from stdin) |
| `wt-memory recall "query" [--mode MODE] [--tags t1,t2]` | Semantic search with recall modes and tag filtering |
| `wt-memory list [--type TYPE] [--limit N]` | List memories with optional filters (JSON) |
| `wt-memory forget <id>` | Delete a single memory by ID |
| `wt-memory forget --all --confirm` | Delete all memories (requires --confirm) |
| `wt-memory forget --older-than <days>` | Delete memories older than N days |
| `wt-memory forget --tags <t1,t2>` | Delete memories matching tags |
| `wt-memory context [topic]` | Condensed summary by category |
| `wt-memory brain` | 3-tier memory visualization |
| `wt-memory get <id>` | Get a single memory by ID |
| `wt-memory export [--output FILE]` | Export all memories to JSON (stdout or file) |
| `wt-memory import FILE [--dry-run]` | Import memories from JSON (skip duplicates) |
| `wt-memory sync` | Push + pull memories via git remote |
| `wt-memory sync push` | Push memories to shared team branch |
| `wt-memory sync pull` | Pull memories from shared team branch |
| `wt-memory sync status` | Show sync status (local vs remote counts) |
| `wt-memory proactive` | Generate proactive context for current session |
| `wt-memory stats` | Show memory statistics (counts, types, noise ratio) |
| `wt-memory cleanup` | Delete low-importance and noisy memories |
| `wt-memory migrate` | Run pending memory storage migrations |
| `wt-memory migrate --status` | Show migration history |
| `wt-memory repair` | Repair index integrity |
| `wt-memory audit [--threshold N] [--json]` | Report duplicate clusters and redundancy stats |
| `wt-memory dedup [--threshold N] [--dry-run] [--interactive]` | Remove duplicate memories |
| `wt-memory status [--json]` | Show memory config, health, and count |
| `wt-memory projects` | List all projects with memory counts |
| `wt-memory metrics [--since Nd] [--json]` | Injection quality report |
| `wt-memory dashboard [--since Nd]` | Generate HTML dashboard |
| `wt-memory rules add --topics "t1,t2" "content"` | Add a deterministic rule |
| `wt-memory rules list` | List rules |
| `wt-memory rules remove <id>` | Remove a rule |

## OpenSpec

| Command | Description |
|---------|-------------|
| `wt-openspec status [--json]` | Show OpenSpec change status |
| `wt-openspec init` | Initialize OpenSpec in the project |
| `wt-openspec update` | Update OpenSpec skills to latest version |

## Design

| Command | Description |
|---------|-------------|
| `wt-figma-fetch <docs-dir>` | Scan `docs-dir/**/*.md` for Figma URLs, fetch raw data + assemble `design-snapshot.md` |
| `wt-figma-fetch <url> -o <dir>` | Fetch a single Figma file into a directory |
| `wt-figma-fetch --force <docs-dir>` | Re-fetch even if snapshots already exist |
| `wt-figma-fetch --reprocess <docs-dir>` | Re-assemble snapshots from existing raw data (no MCP calls) |

Output per Figma file goes to `<docs-dir>/figma-raw/<file-key>/` with raw MCP responses and per-file `design-snapshot.md`. A combined snapshot is written to `./design-snapshot.md` (project root) for pipeline compatibility.

Prerequisites: Figma MCP authenticated in Claude Code (`~/.claude/.credentials.json`), Python `mcp` SDK installed.

## Utilities

| Command | Description |
|---------|-------------|
| `wt-config editor list` | List supported editors and availability |
| `wt-config editor set <name>` | Set preferred editor |
| `wt-usage` | Show Claude API token usage |
| `wt-version` | Display version info (branch, commit, date) |
| `wt-deploy-hooks <target-dir>` | Deploy Claude Code hooks to a directory |

<details>
<summary>Internal scripts (not for direct use)</summary>

These are called by other tools or by Claude Code hooks:

- `wt-common.sh` — shared shell functions
- `wt-hook-skill` — UserPromptSubmit hook (skill tracking)
- `wt-hook-stop` — Stop hook (timestamp refresh + memory reminder)
- `wt-hook-memory-recall` — automatic memory recall on prompts
- `wt-hook-memory-save` — automatic memory save on session end
- `wt-hook-memory-warmstart` — session start memory warmup
- `wt-hook-memory-pretool` — pre-tool hot-topic recall
- `wt-hook-memory-posttool` — post-tool error recall
- `wt-skill-start` — register active skill for status display
- `wt-control-gui` — GUI launcher (called by `wt-control`)
- `wt-completions.bash` / `wt-completions.zsh` — shell completions
- `wt-memory-hooks check/remove` — legacy inline hook management

</details>

---

*See also: [Getting Started](getting-started.md) · [Configuration](configuration.md) · [Worktree Management](worktrees.md)*
