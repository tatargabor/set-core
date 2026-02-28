## hook-activity-path

Move activity tracking from per-project relative file to PATH-based hook.

### Requirements

- MUST create `bin/wt-hook-activity` with the same logic as `.claude/hooks/activity-track.sh`
- MUST read PreToolUse hook JSON from stdin (skill name, args extraction)
- MUST write `.claude/activity.json` with skill, skill_args, broadcast, modified_files, updated_at
- MUST throttle writes (10s minimum between updates)
- MUST preserve existing broadcast and modified_files fields when updating
- MUST be executable and follow the same shebang/structure as other `wt-hook-*` scripts
