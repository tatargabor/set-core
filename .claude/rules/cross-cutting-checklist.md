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

- **`git add <path>` is NOT enough — `git commit` commits the whole INDEX.** Measured
  2026-08-20, in this repository, minutes after the paragraph above was written: a
  commit staged with one explicit path still carried a parallel thread's archive
  (6 renames + 2 new spec files, 193 lines), because that thread had already
  **staged** its work when the commit ran. Adding the right path does not unstage
  somebody else's.
- **Use a pathspec-limited commit**: `git commit <path> <path> -m …`, which ignores
  the index and commits only those paths. `git add <path>` then `git commit` does not.
- **List paths explicitly**: `git add <path> <path>` — or `git add -u <path>`.
- **Two caveats on that pathspec-limited commit, both measured.** It fails with
  `pathspec … did not match any file(s) known to git` for a path git does not yet
  track, so **`git add` is still required first** — the pathspec goes on the commit
  *in addition to* the add, never instead of it. And it commits the WORKING TREE
  content of those paths, so a partial hunk staged with `git add -p` goes in whole.
- **`git stash` with no pathspec is the same hazard, and worse.** Measured
  2026-08-20: a stash by one agent removed the other's files from the **working
  tree** — their `git status` went clean and the work sat in a `stash@{0}` they had
  no reason to look in. A commit at least leaves the content in a findable commit.
  Stash your own paths: `git stash push -- <paths>`.
- **A guard now enforces this**, because an instruction is not a constraint:
  `set-hook-checkout-guard` refuses a pathspec-less commit that would carry another
  session's staged work, and refuses the sweeping forms outright. If it blocks you,
  add the pathspec — do not reach for a way around it.
- **Read `git status` before committing** and account for every line. A file you
  did not touch is a stop sign, not noise.
- **If it already happened, do NOT unpick it.** An amend or a reset takes back
  what the other agent is holding right now, which is far more expensive than a
  badly grouped commit. Amend the MESSAGE to say what the commit actually
  contains, so the other side can find it.
