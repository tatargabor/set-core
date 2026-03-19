---
name: set
description: Manage git worktrees for parallel AI agent development. Use this when asked to create, list, open, close, or merge worktrees, or when working with set-* commands.
---

# Worktree Management Skill

Manage git worktrees for parallel AI agent development.

## Context Detection

First, detect which mode you're operating in:

```bash
# Check if we're in a worktree (not the main repo)
if git rev-parse --is-inside-work-tree &>/dev/null; then
  BRANCH=$(git branch --show-current)
  if [[ "$BRANCH" == change/* ]]; then
    CHANGE_ID="${BRANCH#change/}"
    echo "Running in worktree: $CHANGE_ID"
    MODE="worktree"
  else
    echo "Running in main repository"
    MODE="main"
  fi
fi
```

## Central Control Commands

Use these from the main repository to manage worktrees.

### List Worktrees

```bash
set-list
```

List all active worktrees with their change IDs and paths.

To see remote branches available for checkout:
```bash
set-list --remote
```

### Create New Worktree

```bash
set-new <change-id>
```

Creates a new worktree at `../<project>-<change-id>/` with branch `change/<change-id>`.

If the branch exists on remote, it will be checked out and tracked automatically.

To force create a new branch even if remote exists:
```bash
set-new <change-id> --new
```

### Open Worktree for Work

```bash
set-work <change-id>
```

Opens the worktree in Zed editor with Claude Code. This launches a new agent session in that worktree context.

To open in terminal instead:
```bash
set-work <change-id> --terminal
```

### Close Worktree

```bash
set-close <change-id>
```

Removes the worktree. Interactive mode asks what to do with the branch:
1. Keep branch (can reopen later)
2. Delete local branch only
3. Delete local and remote branch

Non-interactive options:
```bash
set-close <change-id> --keep-branch      # Keep the branch
set-close <change-id> --delete-remote    # Delete both local and remote
```

### Merge Worktree

```bash
set-merge <change-id>
```

Merges the worktree branch into the target branch (default: main/master).

Options:
```bash
set-merge <change-id> --target develop   # Merge to specific branch
set-merge <change-id> --no-delete        # Keep branch after merge
```

## Self-Control Commands

Use these from within a worktree to manage your own state.

### Push Current Branch

```bash
git push -u origin $(git branch --show-current)
```

Pushes the current branch to remote and sets up tracking.

### Get Current Change ID

```bash
CHANGE_ID=$(git branch --show-current | sed 's|change/||')
echo "Current change: $CHANGE_ID"
```

### Close Own Worktree

From within a worktree, you cannot directly close it (the directory is in use). Instead:

1. Commit and push your changes
2. Exit the agent session
3. From main repo, run: `set-close <change-id>`

Or instruct the user:
```
To close this worktree after I exit:
  cd <main-repo-path>
  set-close <change-id>
```

### Merge Own Work

```bash
CHANGE_ID=$(git branch --show-current | sed 's|change/||')
set-merge "$CHANGE_ID"
```

This will merge your current branch to the target and optionally close the worktree.

## Workflow Examples

### Central Agent: Create and Delegate Work

```bash
# List current work items
set-list

# Create new worktree for a task
set-new fix-login-bug

# Open agent in that worktree
set-work fix-login-bug
```

### Worktree Agent: Complete and Hand Off

```bash
# Check current context
git branch --show-current  # -> change/fix-login-bug

# Do work...
# ...

# Push changes
git push -u origin change/fix-login-bug

# Report back to user that work is ready for merge
echo "Work complete. To merge: set-merge fix-login-bug"
```

### Full Lifecycle

```bash
# 1. Central agent creates worktree
set-new implement-feature

# 2. Central agent opens worktree for work
set-work implement-feature

# 3. Worktree agent does the work, pushes
git add -A && git commit -m "Implement feature"
git push -u origin change/implement-feature

# 4. Central agent merges when ready
set-merge implement-feature

# 5. Worktree is cleaned up automatically (or use set-close)
```

## Project Health Audit

### Scan Project Health

```bash
set-audit scan              # Human-readable report
set-audit scan --json       # Machine-readable JSON
set-audit scan --condensed  # Summary line only
```

Scans 6 project health dimensions:
- **Claude Code Config** — permissions, hooks, agents, rules
- **Design Documentation** — docs/design/*.md coverage
- **OpenSpec Config** — config.yaml context population
- **Code Quality Signals** — large files, unused code tooling
- **CLAUDE.md Structure** — conventions, managed sections
- **Gitignore Coverage** — sensitive file patterns

Output includes evidence (what exists), delta (✅/⚠️/❌), and guidance (source pointers for what the LLM should READ to create missing content).

### Interactive Remediation

Use `/set:audit` to scan and interactively address gaps. The skill runs the scan, presents findings, and helps create project-specific content by reading the actual codebase — not templates.

## Orchestration Supervisor

### Sentinel (Agent Mode)

Use `/set:sentinel` to start and supervise a `set-orchestrate` run with intelligent monitoring. The agent starts the orchestrator in background, polls state every 15s, and makes decisions on crashes (log diagnosis), checkpoints (auto-approve periodic), and completion (summary report).

```bash
/set:sentinel                                    # basic supervision
/set:sentinel --spec docs/v5.md --max-parallel 3 # with options
```

### Sentinel (Bash Fallback)

For environments without Claude agent access:

```bash
set-sentinel                                      # basic crash recovery
set-sentinel --spec docs/v5.md --max-parallel 3   # with options
```

See `docs/sentinel.md` for full documentation.
