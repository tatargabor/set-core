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

## Committing in a tree somebody else is working in

**`git add -A` does not mean "all my changes" — it means "all changes."** Several
agents in one checkout is ordinary here, not an edge case, and the sweep is
silent: nothing warns, the commit succeeds, and the tests pass because the other
agent's work was fine too.

Measured 2026-08-20: a commit for one change carried a parallel thread's
in-progress `fleetTileClick.ts` (+29) and its test (+68). The content survived,
but the other thread's `git status` then showed CLEAN — which reads as "my work
is gone" or "somebody took it", and neither is recoverable from the working tree.

- **List paths explicitly**: `git add <path> <path>` — or `git add -u <path>`.
- **Read `git status` before committing** and account for every line. A file you
  did not touch is a stop sign, not noise.
- **If it already happened, do NOT unpick it.** An amend or a reset takes back
  what the other agent is holding right now, which is far more expensive than a
  badly grouped commit. Amend the MESSAGE to say what the commit actually
  contains, so the other side can find it.
