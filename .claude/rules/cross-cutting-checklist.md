---
# Cross-cutting checklist — deployed as .claude/rules/cross-cutting-checklist.md
# Scoped to paths listed in project-knowledge.yaml cross_cutting_files.
# Claude will see this rule when editing files matching these globs.
globs:
  # Populated by set-project init-knowledge from project-knowledge.yaml
  # Example:
  # - src/i18n/*.json
  # - src/components/Sidebar.tsx
---

# Cross-Cutting File Checklist

When modifying a cross-cutting file (one shared across multiple features), verify:

- [ ] Changes are additive — don't remove or rename entries other features depend on
- [ ] No duplicate keys or entries introduced
- [ ] Ordering conventions are maintained (alphabetical, grouped, etc.)
- [ ] If adding to a list/map, check for existing similar entries to avoid duplication
- [ ] Parallel changes: check if other worktrees may be modifying this same file
