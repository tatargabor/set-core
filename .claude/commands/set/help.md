When the user asks about set-core features, use this quick reference to answer. For deeper details, read the linked files or run `set-<command> --help`.

## CLI Commands

| Command | Description |
|---------|-------------|
| `set-new <change-id>` | Create a git worktree for a spec change |
| `set-list` | List active worktrees for projects |
| `set-work <change-id>` | Open editor for a worktree (creates if needed) |
| `set-close <change-id>` | Remove a worktree and optionally its branch |
| `set-merge <change-id>` | Merge a worktree's branch into a target branch |
| `set-status` | Display worktree and Claude agent status |
| `set-loop <command>` | Run autonomous agent loop in a worktree |
| `set-memory <command>` | Per-project cognitive memory (shodh-memory). Details: `docs/developer-memory.md` |
| `set-control` | Launch the Control Center GUI |
| `set-project <command>` | Project management (init, deploy) |
| `set-openspec <command>` | OpenSpec CLI wrapper (status, init, update) |
| `set-usage` | Show Claude API usage and burn rate |
| `set-config <command>` | Configure set-core settings |
| `set-add [path]` | Add an existing git repo to set-core |
| `set-focus <change-id>` | Focus the editor window for a worktree |
| `set-run-logs <run-id>` | Forensic analysis of a completed orchestration run (discover/digest/session/grep/orchestration) |
| `set-version` | Display set-core version |

## Skills (Slash Commands)

### OpenSpec Workflow (`/opsx:*`)

| Skill | Description |
|-------|-------------|
| `/opsx:new` | Start a new change with structured artifacts (proposal → design → specs → tasks) |
| `/opsx:ff` | Fast-forward: create all artifacts in one go, ready for implementation |
| `/opsx:apply` | Implement tasks from a change |
| `/opsx:continue` | Continue working on a change — create the next artifact |
| `/opsx:verify` | Verify implementation matches change artifacts |
| `/opsx:archive` | Archive a completed change (syncs specs, cleans up) |
| `/opsx:bulk-archive` | Archive multiple completed changes at once |
| `/opsx:explore` | Open-ended thinking/exploration mode (no implementation) |
| `/opsx:sync` | Sync delta specs from a change to main specs |
| `/opsx:onboard` | Guided walkthrough of the OpenSpec workflow |

### Worktree Management (`/set:*`)

| Skill | Description |
|-------|-------------|
| `/set:new` | Create a new worktree |
| `/set:work` | Open a worktree for editing |
| `/set:list` | List all worktrees |
| `/set:close` | Close a worktree |
| `/set:merge` | Merge a worktree into target branch |
| `/set:push` | Push current branch to remote |
| `/set:status` | Show agent and worktree status |
| `/set:loop` | Start autonomous agent loop (Ralph) |
| `/set:broadcast` | Broadcast what you're working on to other agents |
| `/set:msg` | Send a directed message to another agent |
| `/set:inbox` | Read incoming messages |
| `/set:memory` | Interact with project memory system |
| `/set:forensics` | Post-run debugging — error triage on a completed orchestration run |
| `/set:help` | This quick reference |

## MCP Tools

### Memory (`set-memory`)

| Tool | Description |
|------|-------------|
| `remember(content, type, tags)` | Save a memory (types: Decision, Learning, Context) |
| `recall(query, mode, tags)` | Semantic search for memories |
| `proactive_context(context)` | Context-aware memory retrieval with relevance scores |
| `forget(id)` | Delete a memory |
| `forget_by_tags(tags)` | Bulk delete by tags |
| `list_memories(type)` | List memories, optionally filtered by type |
| `get_memory(id)` | Get full details of a single memory |
| `context_summary(topic)` | Condensed summary by category |
| `brain()` | 3-tier memory visualization (core/active/peripheral) |
| `audit(threshold)` | Duplicate detection report |
| `cleanup(threshold, dry_run)` | Remove low-value memories |
| `dedup(threshold, dry_run)` | Remove duplicate memories |
| `add_todo(content, tags)` | Save a todo for later |
| `list_todos()` | List open todos |
| `complete_todo(id)` | Mark a todo as done |
| `sync()` | Push + pull memory sync (git-based) |
| `export_memories()` | Export all memories to JSON |

### Worktree & Team (`set-core`)

| Tool | Description |
|------|-------------|
| `list_worktrees()` | List all git worktrees across projects |
| `get_activity(change_id)` | Get agent activity from local worktrees |
| `get_team_status()` | Show which team members are active and what they're doing |
| `get_ralph_status(change_id)` | Get Ralph loop status for a worktree |
| `send_message(recipient, message)` | Send a directed message to another agent |
| `get_inbox(since)` | Read incoming directed messages |
| `get_worktree_tasks(worktree_path)` | Get tasks.md content from a worktree |

## Common Workflows

**New feature (full workflow):**
`set-new my-feature` → `/opsx:ff` → `/opsx:apply` → `/opsx:verify` → `/opsx:archive` → `set-merge my-feature`

**Quick fix (skip artifacts):**
`set-new quick-fix` → implement → `set-merge quick-fix`

**Explore before deciding:**
`/opsx:explore` → think/investigate → `/opsx:new` when ready

**Parallel work:**
`set-new feature-a` + `set-new feature-b` → work in separate worktrees → merge independently

## Detailed Documentation

| Topic | File |
|-------|------|
| Memory system | `docs/developer-memory.md` |
| Agent messaging | `docs/agent-messaging.md` |
| Configuration | `docs/config.md` |
| README guide | `docs/readme-guide.md` |
