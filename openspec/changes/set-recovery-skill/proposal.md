# Proposal: set-recovery skill

## Problem

When an orchestration run fails late (review found design issues, integration bug discovered), there is currently **no way to roll back** to a known-good state and re-run only the failed changes. The only options are:

1. **Continue forward** — accept the broken state, fix-forward (slow, costly)
2. **Re-run from scratch** — wastes the work of all earlier merged changes (very expensive)
3. **Manual rollback** — git reset, worktree cleanup, openspec archive un-do, state.json edit — error-prone, easy to corrupt state

### Real example: minishop-run1

- Changes 1-4 (foundation, auth, product-catalog, shopping-cart) merged with **good design** ✓
- Change 5 (admin-products) merged with **broken design** (light sidebar instead of dark) — agent context drifted across retries ✗
- Change 6 (checkout-orders) inherited the broken design ✗
- We want to: **rollback to after shopping-cart, re-run admin-products + checkout-orders** with the resume preamble fix

Currently this requires manual git surgery in 6+ places. We need a safe, automated tool.

## Solution

A new CLI tool `set-recovery` that rolls back a project to the state immediately after a specific change was archived. Everything from then on is undone safely.

### Usage

```bash
# Rollback so admin-products and everything after is undone, restored to pending
set-recovery <project-name> shopping-cart

# Preview without making changes
set-recovery <project-name> shopping-cart --dry-run

# Force without confirmation (for scripts)
set-recovery <project-name> shopping-cart --yes
```

### What it does

| Layer | Action |
|-------|--------|
| **Git** | `git reset --hard <archive-commit-of-target>` on main branch |
| **Branches** | Delete `change/*` branches for rolled-back changes |
| **Worktrees** | `git worktree remove --force` for rolled-back worktrees |
| **OpenSpec** | Move archived changes back from `openspec/changes/archive/` → `openspec/changes/` |
| **State** | Reset rolled-back changes in `orchestration-state.json` to `status=pending`, clear retry counts, gate results, ralph_pid, worktree_path, tokens, etc. |
| **Merge queue** | Clear |
| **Phase** | Reset to the phase of the first rolled-back change |
| **Checkpoints** | Remove checkpoints created after the rollback point |
| **Backup** | Save state.json + a git tag `recovery-backup-{timestamp}` for undo |

### What it does NOT touch

- Consumer project files outside the run dir
- Memory entries (they're date-keyed, not tied to specific changes)
- The digest, plan, test-plan.json (still valid)
- Event log (kept as audit trail)
- Sentinel session files

## Skill / CLI design

**Bash CLI**: `bin/set-recovery` calls Python module `lib/set_orch/recovery.py`

**Skill**: `.claude/skills/set-recovery/SKILL.md` documents usage for Claude Code agents

**Slash command**: `/set:recovery <change>` invokes the skill in the active project

## Safety guarantees

1. **Dry-run by default-ish**: full preview shown before any destructive action
2. **State backup**: `orchestration-state.json` copied to `.bak.<timestamp>`
3. **Git safety tag**: `recovery-backup-{timestamp}` created before reset (recoverable via reflog)
4. **Confirmation prompt**: requires explicit `yes` (skipped only with `--yes`)
5. **Atomic**: if any step fails mid-way, rollback the partial recovery (state.json restored from backup)
6. **Refuses if project still running**: must stop sentinel/orchestrator first
7. **Refuses if target change is not merged**: can't rollback to a state that didn't exist

## Why a separate change

This is a non-trivial new tool with its own CLI, Python module, skill, and edge cases. Not appropriate to bolt onto another change.

## Risk

- Medium: destructive git operations on main
- Mitigated by: backup tags, dry-run preview, explicit confirmation, atomic failure handling
