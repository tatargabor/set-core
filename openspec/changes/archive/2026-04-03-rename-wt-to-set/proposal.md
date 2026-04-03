# Proposal: Rename wt/ to set/

## Why

The project config directory is called `wt/` (from legacy "worktree tools") but the tool is called "SET". Every other convention uses `set-` prefix (set-project, set-orchestrate, .set/). The `wt/` name is confusing — users don't know what it means.

## What Changes

- **Rename `wt/` directory to `set/`** in all project scaffolds, templates, and path references
- **Auto-migration in `set-project init`**: detect `wt/` → rename to `set/`
- **Update all hardcoded `"wt/"` paths** in Python, bash, templates, skills
- **Keep backwards compat**: code checks `set/` first, falls back to `wt/`

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `wt-directory-structure` — renamed paths from `wt/` to `set/`

## Impact

- `bin/set-project` — ~38 path references
- `lib/set_orch/*.py` — ~25 path references across 14 files
- `modules/web/templates/` — directory rename + manifests
- `.claude/skills/` — ~11 references
- `tests/` — ~60 references
- Consumer projects auto-migrated on next `set-project init`
