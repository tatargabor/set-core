## skill-hook-automation (delta)

Add auto-commit instruction to CLAUDE.md template and apply skill.

### Changes

- `deploy_set_tools()` in `bin/set-project` MUST add an "Auto-Commit After Apply" section to CLAUDE.md with:
  - Marker: `## Auto-Commit After Apply`
  - Instruction: after skill-driven apply finishes or pauses, commit all changes
  - Idempotent: skip if marker already present (same pattern as memory marker)
- `.claude/skills/openspec-apply-change/SKILL.md` MUST add Step 8: commit changes after implementation
- `.claude/commands/opsx/apply.md` MUST add the same Step 8 (both files must stay in sync)
- The commit step MUST instruct the agent to: stage relevant files, write a concise commit message, follow standard commit flow
