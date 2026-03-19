[< Back to README](../README.md)

# Worktree Management

Git worktrees let you work on multiple branches simultaneously — each in its own directory, with its own editor and Claude Code session. set-core wraps git worktree commands with editor integration, Claude Code auto-launch, and status tracking.

## CLI Commands

| Command | Description |
|---------|-------------|
| `set-new <change-id>` | Create new worktree + branch (`change/<change-id>`) |
| `set-work <change-id>` | Open worktree in editor + start Claude Code |
| `set-close <change-id>` | Close worktree (removes directory and branch) |
| `set-merge <change-id>` | Merge worktree branch back to main |
| `set-add [path]` | Add existing repo or worktree to set-core |
| `set-list` | List all active worktrees |
| `set-status` | JSON status of all worktrees and agents |
| `set-focus <change-id>` | Focus editor window for a worktree |

## Claude Code Skills

Every CLI command has a matching slash command — manage worktrees without leaving the agent:

| Skill | CLI Equivalent |
|-------|---------------|
| `/set:new <change-id>` | `set-new` |
| `/set:work <change-id>` | `set-work` |
| `/set:list` | `set-list` |
| `/set:close <change-id>` | `set-close` |
| `/set:merge <change-id>` | `set-merge` |

## Typical Workflow

```bash
# Create a worktree for a new feature
set-new add-user-auth

# Open it — editor + Claude Code launch automatically
set-work add-user-auth

# ... work on the feature ...

# Merge back to main when done
set-merge add-user-auth

# Clean up
set-close add-user-auth
```

## Parallel Feature Development

You have a big feature and a bug to fix. Instead of stashing and switching branches, create two worktrees:

```bash
set-new add-user-auth     # worktree 1: big feature
set-new fix-login-bug     # worktree 2: quick bugfix
```

Each gets its own directory, branch, and Claude session. Work on the bugfix, merge it, close it — while the auth feature keeps going untouched.

```bash
set-merge fix-login-bug   # merge bugfix to main
set-close fix-login-bug   # clean up
# add-user-auth is still there, agent still has context
```

## Stay in the Agent

Every set-core operation has a matching Claude Code slash command:

```
> /set:new fix-payment-bug       # creates worktree, stay in Claude
> /set:list                       # see all worktrees
> /set:merge fix-payment-bug      # merge back when done
> /set:close fix-payment-bug      # clean up
```

The MCP server also lets your agent see what other worktrees and agents are doing — check team status, read other worktrees' task lists, and see Ralph loop progress without leaving the conversation.

## Editor Configuration

```bash
set-config editor list           # list supported editors
set-config editor set <name>     # set preferred editor (zed, vscode, cursor, windsurf)
```

`set-work` and GUI double-click open the worktree in the configured editor and start Claude Code automatically.

---

*See also: [Getting Started](getting-started.md) · [Ralph Loop](ralph.md) · [CLI Reference](cli-reference.md) · [Control Center GUI](gui.md)*
