## Why

`set-project init` / `wt-deploy-hooks` deploys hook configurations (settings.json) that reference `.claude/hooks/activity-track.sh`, but never copies the actual file to target projects. This causes silent hook failures in 11/13 deployed projects. Additionally, the CLAUDE.md generator only includes the Persistent Memory section but omits the "Auto-Commit After Apply" instruction, causing agents to implement hundreds of files without ever committing. The `opsx:apply` skill definition also lacks a commit step.

## What Changes

- **Rename `.claude/hooks/activity-track.sh` to `bin/wt-hook-activity`** and put it on PATH like all other hooks, eliminating the need for per-project file copying
- **Update `wt-deploy-hooks`** to reference `wt-hook-activity` instead of `.claude/hooks/activity-track.sh` in settings.json
- **Add `wt-hook-activity` to `install.sh`** scripts array for symlinking
- **Add "Auto-Commit After Apply" section to CLAUDE.md template** in `deploy_set_tools()` so all deployed projects get the commit instruction
- **Add commit step (Step 8) to `opsx:apply`** in both SKILL.md and command file

## Capabilities

### New Capabilities
- `hook-activity-path`: Move activity-track.sh to PATH-based hook (`wt-hook-activity`) consistent with all other hooks

### Modified Capabilities
- `hook-auto-install`: Update wt-deploy-hooks to reference PATH-based hook command instead of relative file path
- `skill-hook-automation`: Add auto-commit instruction to CLAUDE.md template and apply skill definition

## Impact

- `bin/wt-hook-activity` — new file (moved from `.claude/hooks/activity-track.sh`)
- `bin/wt-deploy-hooks` — hook_json PreToolUse command path change
- `bin/set-project` — deploy_set_tools() CLAUDE.md snippet addition
- `install.sh` — scripts array addition
- `.claude/skills/openspec-apply-change/SKILL.md` — Step 8 addition
- `.claude/commands/opsx/apply.md` — Step 8 addition
- All registered projects get the fix on next `install.sh` or `set-project init` run
