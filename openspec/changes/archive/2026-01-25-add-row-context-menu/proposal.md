# Change: Add Row Context Menu & Improve New Dialog

JIRA Key: EXAMPLE-559
Story: EXAMPLE-466

## Why
1. Worktree operations (Focus, Close, JIRA, Git) are more easily accessible from a right-click menu
2. Command output visibility - commands shouldn't run in the background

## What Changes

### 1. Row Context Menu

Right-click on a worktree row:

```
Focus Window
Open in Terminal
Open in File Manager
Copy Path
─────────────────
+ New Worktree...
─────────────────
Git →
    Merge to...
    Merge from...
    Push
    Pull
    Fetch
─────────────────
JIRA →
    Open Story
    Log Work...
    Sync Worklog
─────────────────
Worktree →
    Close
    Push Branch
─────────────────
Worktree Config...
```

### 2. New Worktree Dialog

Simplified dialog (Base Branch removed - wt-new doesn't support it):

```
┌─ New Worktree ─────────────────────┐
│                                     │
│  Project:    [aitools-specdriven ▼] │
│  Change ID:  [__________________]   │
│                                     │
│  Preview:                           │
│  Path: /home/.../project-wt-xxx     │
│  Branch: change/xxx                 │
│                                     │
│          [Cancel]  [Create]         │
└─────────────────────────────────────┘
```

- **Project dropdown**: list of registered projects
- **Change ID**: the change identifier (branch name: `change/<id>`)
- **Preview**: full path and branch name

### 3. Merge Dialog

Git → Merge to... new dialog with options:

```
┌─ Merge Branch ────────────────────┐
│                                    │
│  Source: change/add-feature        │
│  Merge into: [master ▼]            │
│                                    │
│  ⚠ Uncommitted changes detected    │
│  ☑ Stash uncommitted changes       │
│  ☑ Keep source branch (no delete)  │
│                                    │
│          [Cancel]  [Merge]         │
└────────────────────────────────────┘
```

- Stash is automatically checked if there are changes
- Keep source branch is checked by default (--no-delete)

### 4. Merge From

Git → Merge from... pulls in another branch:
- change/* branches listed first
- Fetch + merge origin/branch

### 5. Worktree Config Dialog

Editable config files from the worktree's `.set-core/` directory:
- Tabs: Jira, Confluence, etc.
- Editable fields + Save button

### 6. State Persistence

The "needs attention" state persists after restart:
- `~/.config/set-core/gui-state.json`
- needs_attention set + previous_statuses

### 7. Command Output Dialog

Every command (Git, wt-new, wt-close, wt-work, etc.) runs in a dialog:
- Shows the executed command
- Real-time output
- Close button always active (no need to wait for process to finish)

## Impact
- Affected specs: control-center
- Affected code: gui/main.py
