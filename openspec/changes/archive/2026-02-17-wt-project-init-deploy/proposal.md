## Why

`set-project init` only registers the project in `projects.json`. It doesn't deploy hooks, `/wt:*` commands, or wt skills to the project's `.claude/` directory. Currently these are deployed via global symlinks (`~/.claude/commands/wt`) by `install.sh`, which means all projects share one version — breaking when different projects need different set-core versions. There's no single command to set up or update a project's set-core integration.

## What Changes

- Enhance `set-project init` to also deploy the full set-core `.claude/` stack to the target project:
  - Hooks → `.claude/settings.json` (via existing `wt-deploy-hooks`)
  - Commands → `.claude/commands/wt/` (copy from set-core repo)
  - Skills → `.claude/skills/wt/` (copy from set-core repo)
- Re-running `set-project init` on an already-registered project skips registration but updates all deployed files (idempotent update)
- Remove global symlinks from `install.sh`'s `install_skills()` — per-project deployment replaces them

## Capabilities

### New Capabilities
- `project-init-deploy`: Per-project deployment of set-core hooks, commands, and skills via `set-project init`

### Modified Capabilities
- `worktree-tools`: `set-project init` gains deployment behavior; re-running on existing project triggers update

## Impact

- `bin/set-project`: `cmd_init` enhanced with deploy logic
- `install.sh`: `install_skills()` no longer creates `~/.claude/commands/wt` and `~/.claude/skills/wt` global symlinks; `install_project_hooks()` folded into the new per-project deploy
- User projects get `.claude/commands/wt/` and `.claude/skills/wt/` as copied files (not symlinks)
