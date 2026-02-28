## hook-auto-install (delta)

Update hook deployment to use PATH-based activity hook.

### Changes

- `wt-deploy-hooks` MUST reference `wt-hook-activity` (PATH-based) instead of `.claude/hooks/activity-track.sh` (relative) in both:
  - The full hook_json template (PreToolUse[Skill] command)
  - The stale downgrade jq expression that re-adds PreToolUse[Skill]
- `install.sh` MUST include `wt-hook-activity` in the scripts array for symlinking to `~/.local/bin/`
