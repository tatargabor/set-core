## 1. Remove legacy current_skill

- [x] 1.1 Remove `current_skill` write from `bin/wt-skill-start` (line that writes to `.set-core/current_skill`). Only keep the per-PID write.
- [x] 1.2 Remove `current_skill` refresh logic from `bin/wt-hook-stop` (the block that reads/refreshes `.set-core/current_skill`). Only keep per-PID refresh.
- [x] 1.3 Remove `current_skill` fallback from `get_agent_skill()` in `bin/wt-status` — if per-PID file doesn't exist, return empty string immediately.

## 2. Add UserPromptSubmit hook (replaces failed PreToolUse/Skill approach)

- [x] 2.1 Rewrite `bin/wt-hook-skill` script: reads UserPromptSubmit JSON from stdin, extracts skill name from `prompt` field via `/skill-name` regex, calls `wt-skill-start <skill-name>`. Exit silently on non-skill prompts.
- [x] 2.2 Add UserPromptSubmit hook entry in `.claude/settings.json` (project-level), running `wt-hook-skill`.
- [x] 2.3 Update `install.sh` to deploy `wt-hook-skill` symlink alongside existing `wt-hook-stop`.
- [x] 2.4 Update `install.sh` hook deployment to add UserPromptSubmit hook and clean up stale PreToolUse/Skill hooks in all managed projects.

## 3. Clean up SKILL.md files

- [x] 3.1 Remove the manual `wt-skill-start` instruction block from all `.claude/skills/*/SKILL.md` files (approx 11 files).

## 4. Skill freshness indicator

- [x] 4.1 Extend `.skill` file format to 3 fields: `name|timestamp|freshness` (fresh/last)
- [x] 4.2 `wt-skill-start`: write `fresh` as 3rd field
- [x] 4.3 `wt-hook-skill`: on non-skill prompts, flip `fresh` → `last` in existing `.skill` file
- [x] 4.4 `wt-hook-stop`: preserve freshness flag when refreshing timestamp
- [x] 4.5 `wt-status`: parse and expose `skill_fresh` field in JSON output
- [x] 4.6 GUI `table.py`: dim skill text (muted color) when `skill_fresh == "last"`
