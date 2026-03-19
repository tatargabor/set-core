## 1. Memory Marker in wt-skill-start

- [x] 1.1 In `bin/wt-skill-start`, after writing the `.skill` file, check if `.claude/skills/<mapped-skill-name>/SKILL.md` contains `set-memory`. If yes, write `.set-core/agents/<pid>.memory` with the skill name. If no, remove any existing `.memory` file for that PID.
- [x] 1.2 Add skill name mapping logic: `opsx:*` → `openspec-*` prefix, `wt:*` → `wt`, other skills → direct name match. Use this to locate the SKILL.md directory.
- [x] 1.3 When writing a new `.skill` file (new skill session), remove the old `.memory` file before checking the new skill.

## 2. Stop Hook Reminder

- [x] 2.1 In `bin/wt-hook-stop`, after the timestamp refresh block, add a check: if `.set-core/agents/<pid>.memory` exists, output `[MEMORY REMINDER] Active skill has set-memory hooks. Run your recall/remember steps before finishing.` to stdout.
- [x] 2.2 Ensure the reminder check runs AFTER the existing timestamp refresh (don't break current behavior).

## 3. Cleanup

- [x] 3.1 In the existing agent cleanup logic (wherever `.skill` files are removed on session end), also remove the corresponding `.memory` file.

## 4. Documentation

- [x] 4.1 Update `docs/` hook documentation with the new `.memory` marker and reminder behavior
- [x] 4.2 Update `docs/readme-guide.md` hooks section with memory reminder hook
- [x] 4.3 Update `README.md` hooks section
