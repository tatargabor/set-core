## Why

Two agent sessions working in one checkout share one git index, and a `git commit`
that names no pathspec publishes whatever *anybody* staged. Measured 2026-08-20
(bug **B-32**): this session staged exactly its own 8 paths, `set-leakscan --staged`
confirmed 8 files, and its `git commit` printed `nothing to commit, working tree
clean` — the 8 files had already left in `066e6233`, a third thread's
*"plan(fleet-pm-mode)"* commit whose message names none of them.

The rule meant to prevent this does not. `.claude/rules/cross-cutting-checklist.md`
prescribes `git add <path>` in place of `git add -A`. Measured in a throwaway repo:
that defends only against sweeping *unstaged* work. When **both** agents staged only
their own file and one then committed without a pathspec, the commit carried both.
The losing side followed the rule exactly and still lost its commit.

Why it is worth a mechanism rather than a stronger sentence: the content survives, so
nothing errors and no test notices. What is destroyed is the *message and the
attribution* — the losing agent's commit, with the evidence it carried, never exists,
and the other side's `git status` reads CLEAN, which is indistinguishable from "my
work is gone". And this repository has already ruled that an instruction is not a
constraint: what an agent cannot do is decided by the tools it holds. The rule was in
the tree this morning and the loss happened twice the same day.

## What Changes

- **New `set-hook-checkout-guard`**, a `PreToolUse` hook on the `Bash` matcher, joining
  `set-hook-leakscan` in the slot that already exists for binding an agent's shell.
- It **measures which paths each session stages** — snapshotting the index either side of
  the session's own staging command and taking the difference, keyed by the `session_id` the
  payload carries (measured: `bin/set-hook-memory:50` already reads that field). It never
  parses the command's arguments, because a glob, a variable, an `xargs` or a script all
  defeat parsing, and each defeat would silently turn the guard into "every commit needs a
  pathspec".
- It **refuses a `git commit` that names no pathspec while the index holds a path the
  committing session did not stage**, and names the remedy — `git commit -- <paths>` —
  in the refusal.
- It **refuses the sweeping forms** outright: `git add -A`, `git add .`,
  `git add -u` with no pathspec, and `git commit -a`.
- It **refuses a pathspec-less `git stash`** while another session's work is present.
  Measured, and it is the worse half of the same hazard: a stash by one agent removed
  the other's files from the **working tree** — their `git status` went clean and the
  work sat in a `stash@{0}` they had no reason to look in. The commit case at least
  leaves the content in a findable commit; this one does not.
- It **stays silent when every staged path belongs to the committing session**, so a
  private checkout with one agent never sees it. A gate that fires daily on nothing
  gets disabled, and that failure mode is already recorded in this repository.
- `.claude/rules/cross-cutting-checklist.md` gains the half it is missing: the
  pathspec belongs on the **commit**, in addition to the `add` — not instead of it.

## Capabilities

### New Capabilities
- `shared-checkout-guard`: refusing a command that would take, publish or move work
  another session in the same checkout is holding, and saying which paths it found and
  what to run instead.

### Modified Capabilities

<!-- None. No existing capability covers the PreToolUse Bash guard slot: the leakscan
     hook that occupies it today has no spec in openspec/specs/ (checked). -->

## Impact

- **New:** `bin/set-hook-checkout-guard`; one entry in `.claude/settings.json` under the
  existing `PreToolUse` / `Bash` matcher; unit tests.
- **Modified:** `.claude/rules/cross-cutting-checklist.md`.
- **Scope, measured — this does not touch orchestration.** Each git worktree carries
  its **own** index (`.git/worktrees/<name>/index`); verified by staging in the main
  tree and committing without a pathspec in a second worktree, where the main tree's
  staged entry survived untouched. So dispatched agents are already immune, and this
  guard protects the one place they are not: several sessions in the same checkout,
  which is how this repository is actually worked on.
- **Not affected:** `git push`/`git tag` gating, which remains `set-hook-leakscan`'s.
  The two hooks answer different questions and neither subsumes the other.
