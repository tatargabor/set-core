## Why

The GUI Control Center's "Skill" column is always empty. The `wt-skill-start` command exists but is not installed to PATH, most SKILL.md files don't call it, and the 30-minute TTL means long sessions lose tracking even if the skill was registered once. There is no mechanism to keep the skill timestamp fresh while an agent is actively working.

## What Changes

- Create `bin/wt-hook-stop` script that refreshes `.set-core/current_skill` timestamp on every Claude `Stop` event
- Add `wt-skill-start` and `wt-hook-stop` to the `install_scripts()` list in `install.sh`
- Add `wt-skill-start <skill-name>` to all opsx SKILL.md files that don't have it
- Create `install_project_hooks()` in `install.sh` that deploys Claude hooks to every registered project's `.claude/settings.json`
- Add hook deployment to `wt-add` so new projects get hooks automatically
- Graceful fallback: hooks exit silently if set-core is not installed

## Capabilities

### New Capabilities
- `skill-tracking-hooks`: Claude Code Stop hook keeps skill timestamp fresh; install deploys hooks to all projects

### Modified Capabilities
- `worktree-tools`: `wt-skill-start` and `wt-hook-stop` added to install script list

## Impact

- `install.sh`: New `install_project_hooks()` function, updated script list
- `bin/wt-add`: Hook deployment on project registration
- `bin/wt-hook-stop`: New script
- `.claude/skills/openspec-*/SKILL.md`: Add `wt-skill-start` calls
- Per-project `.claude/settings.json`: Stop hook configuration added
