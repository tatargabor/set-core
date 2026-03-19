# Proposal: Add Existing Worktrees/Branches

JIRA Key: TBD
Story: TBD

## Summary

Extend the wt tooling to support two new scenarios:
1. **Add existing worktree** - Register an already checked-out git worktree with set-core
2. **Init existing branch** - Initialize a branch for set-core without creating a worktree

## Motivation

Currently `wt-open` creates a new worktree and branch. But users often have:
- Worktrees already checked out manually via `git worktree add`
- Existing branches they want to work on without creating a worktree

These users want to use set-core features (GUI, skills, Ralph loop) without recreating their setup.

## Use Cases

### Use Case 1: Add Existing Worktree

User has manually created a worktree:
```bash
git worktree add ../myproject-wt-feature feature/auth
```

Now they want to register it with set-core:
```bash
cd ../myproject-wt-feature
wt-add  # or: set-project add-worktree
```

Result:
- Worktree appears in Control Center GUI
- Can use /wt skills on it
- Can start Ralph loop on it
- OpenSpec init is called if not present

### Use Case 2: Init Branch Without Worktree

User has an existing branch they want to prepare for set-core:
```bash
wt-init feature/auth  # Initialize branch for set-core, no worktree created
```

Result:
- Branch is tracked by set-core
- If user later creates a worktree from this branch, it's recognized
- OpenSpec init is done on the main repo for this branch

## Proposed Commands

### `wt-add` - Add Existing Worktree

```bash
# From within the worktree directory
wt-add

# Or specify path
wt-add /path/to/worktree

# Options
wt-add --project myproject  # Associate with specific project
```

**What it does:**
1. Validates current directory (or specified path) is a git worktree
2. Extracts change-id from branch name or directory name
3. Registers with set-core (projects.json worktrees section)
4. Runs `openspec init` if not already initialized
5. Shows confirmation

### `wt-init` - Init Branch Without Worktree

```bash
# Initialize existing branch
wt-init feature/auth

# Initialize with change-id alias
wt-init feature/auth --as add-auth
```

**What it does:**
1. Validates branch exists (locally or remote)
2. Creates change metadata in main repo's `.set-core/` directory
3. Runs openspec init for the change (in main repo context)
4. Branch is now "known" to set-core

## Implementation Details

### Detecting Existing Worktree

```bash
# Check if directory is a worktree
git rev-parse --is-inside-work-tree  # true
git rev-parse --git-dir              # points to .git file (not directory)
cat .git                              # gitdir: /path/to/main/.git/worktrees/name
```

### Change-ID Extraction

Priority order:
1. `--as <change-id>` flag (explicit)
2. Directory name pattern: `*-wt-<change-id>` → extract change-id
3. Branch name pattern: `change/<change-id>` → extract change-id
4. Branch name pattern: `feature/<name>` → use name as change-id
5. Prompt user

### Storage Changes

```json
// ~/.config/set-core/projects.json
{
  "projects": {
    "myproject": {
      "path": "/home/user/myproject",
      "worktrees": {
        "add-auth": {
          "path": "/home/user/myproject-wt-add-auth",
          "branch": "change/add-auth",
          "added_manually": true  // Flag for manually added worktrees
        }
      },
      "branches": {
        "feature/auth": {
          "change_id": "add-auth",
          "initialized_at": "2026-01-29T12:00:00Z"
        }
      }
    }
  }
}
```

## Skill Integration

### /wt:add Skill

```
/wt:add [path]

Add an existing git worktree to set-core.
If no path provided, uses current directory.
```

### /wt:init Skill

```
/wt:init <branch> [--as <change-id>]

Initialize an existing branch for set-core without creating a worktree.
```

## GUI Integration

- **"Add" button** in bottom button bar (next to "New" and "Work")
  - Opens folder browser dialog
  - Calls `wt-add` with selected path
  - Refreshes worktree list on success
- Existing worktrees added via `wt-add` appear in Control Center
- "Add Existing Worktree" menu item in project context menu
- "Initialize Branch" dialog accessible from main menu

## Edge Cases

1. **Already registered** - Show message, don't duplicate
2. **Not a worktree** - Error with helpful message
3. **Orphan worktree** (main repo deleted) - Error with explanation
4. **Branch doesn't exist** - Error, suggest creating it first
5. **Remote-only branch** - Offer to create local tracking branch

## Out of Scope

- Migrating existing worktrees from other tools
- Automatic discovery of all worktrees (could be future feature)
- Bulk import
