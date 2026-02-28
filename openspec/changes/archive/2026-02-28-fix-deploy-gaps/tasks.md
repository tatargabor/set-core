## 1. Activity hook PATH migration

- [x] 1.1 Create `bin/wt-hook-activity` — copy content from `.claude/hooks/activity-track.sh`, update header comment to match other `wt-hook-*` scripts style
- [x] 1.2 Update `install.sh` — add `wt-hook-activity` to the `scripts` array in `install_scripts()`
- [x] 1.3 Update `bin/wt-deploy-hooks` — change `hook_json` PreToolUse[Skill] command from `.claude/hooks/activity-track.sh` to `wt-hook-activity`
- [x] 1.4 Update `bin/wt-deploy-hooks` — change the stale downgrade jq expression (line ~271) from `.claude/hooks/activity-track.sh` to `wt-hook-activity`

## 2. CLAUDE.md auto-commit template

- [x] 2.1 Add auto-commit snippet to `bin/wt-project` `deploy_wt_tools()` — after the memory section, add `## Auto-Commit After Apply` section with idempotent marker check (same pattern as `memory_marker`)

## 3. Apply skill commit step

- [x] 3.1 Add Step 8 to `.claude/skills/openspec-apply-change/SKILL.md` — after Step 7, add commit instruction
- [x] 3.2 Add Step 8 to `.claude/commands/opsx/apply.md` — same commit instruction (must match SKILL.md)
