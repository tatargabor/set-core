## Context

The project registry (`~/.config/set-core/projects.json`) is append-only in practice: every
`set-project init` and every E2E runner adds an entry, and nothing ever removes one. Measured
2026-07-24 — 50 entries, 12 of them pointing at directories that no longer exist, ~17 more
being old E2E runs. Separately, `git worktree list --porcelain` reports 10 orphaned worktree
records across two registered projects, all flagged `prunable`.

The user's constraint is the design's hardest input, stated verbatim: *"nem veszhet el a
lemezről worktree vagy file, nem törölhetünk létező könyvtarhoz tartozó projektet.
körültekintőnek kell lenni."* — nothing may be lost from disk; a project whose directory
exists may not be deleted; be careful.

That constraint is not a preference to honour in the implementation. It is the thing the
design has to make *structurally impossible to violate*, because a cleanup tool's failure
direction is catastrophic and silent: what it destroys leaves no trace of having been there.

## Goals / Non-Goals

**Goals:**
- Remove registry entries whose directory is gone, and orphaned git worktree records.
- Make the loss-free guarantee enforceable by test rather than by review.
- Give live-directory projects a reversible way out of the dashboard (archive, not delete).
- One implementation shared by CLI and API, so the guarantee cannot hold in one and not the
  other.

**Non-Goals:**
- Deleting any file, directory, worktree or branch. Not behind a flag, not with `--force`.
- Replacing `set-cleanup` (worktree GC for merged changes) — different job, stays as is.
- Deciding what is "abandoned" by heuristics. The tool acts on *facts* (does the directory
  exist) or on *explicit operator instruction* (the archive flag), never on inference.
- Touching `DELETE /api/projects/{name}`, which is an operator's deliberate act.

## Decisions

### D1 — Deregistration keys on one fact: the directory does not exist

The sole condition is `not os.path.isdir(path)`. Not "is empty", not "has no git", not "is
old". Anything richer is a heuristic, and a heuristic that guesses wrong here deletes an
operator's registration for a live project.

*Alternative rejected:* also deregistering entries whose directory exists but has no `.set/`
or no orchestration state. That would have caught more of the 50 — and it would have caught
`itline-web`, a real project last touched 10h ago.

### D2 — A missing parent directory means "unknown", not "gone"

`os.path.isdir()` returns False both for a deleted directory and for one whose filesystem is
not mounted. The two are indistinguishable at the leaf, and they demand opposite actions.

So deregistration additionally requires that the entry's **parent directory exists**. A
deleted scaffold at `/tmp/tmp.INGbqLloeb` has a live parent (`/tmp`) and is deregistered; an
unmounted `/mnt/nas/proj` has a missing parent and is reported as *unknown* and left alone.

This is the `evidence-discipline.md` "gap is not a zero" rule applied to the filesystem:
absence of evidence about a path is not evidence that the path is gone. The failure direction
picks the answer — being wrong toward "keep" costs a stale row in a list; being wrong toward
"remove" costs an operator's registration with no record that it existed.

### D3 — Archive means the entry stays; only the display changes

Old E2E runs exist on disk, so D1 excludes them by construction. They are marked
`archived: true` + `archivedAt: <iso>` in their existing registry entry. Nothing is removed
from `projects.json`, nothing is touched on disk, and clearing the flag restores the previous
state exactly.

*Alternative rejected:* moving archived entries to a separate `archived.json`. A second file
is a second place, and the two drift — the defect class `evidence-discipline.md` names
directly. One file, one flag.

### D4 — Location separates E2E runs from real projects; age cannot

Archiving is restricted to projects under the framework's own `e2e-runs/` root
(`~/.local/share/set-core/e2e-runs/`), *and* older than an operator-supplied threshold. Both
conditions, because either alone is wrong.

Measured, and this is why: `sales-raketa` (62d) and `minishop0412` (62d) are real projects
exactly as old as the E2E runs to be archived. **Age does not separate them.** The E2E root
is a set-core-owned directory whose contents are by definition test fixtures, so location
does separate them — and it is a framework path, not a consumer-specific one, so it does not
violate the domain boundary.

The threshold has **no default**. An operator who wants archiving states the age; a bare
`set-project prune` can never archive anything.

### D5 — `git worktree prune`, never `git worktree remove`

`prune` discards administrative records for worktrees whose directory is already gone; it
does not touch existing directories and does not delete branches. `remove` deletes a
directory. Only the former appears in this code.

Measured on the 10 orphans: each belongs to a `change/*` branch, and those branches (with
their commits) survive the prune — the worktree record is the only thing discarded. Before
pruning, the tool re-reads `git worktree list --porcelain` and acts only on entries git
itself has flagged `prunable`; a repository with zero prunable entries is skipped without
invoking git at all.

### D6 — The guarantee is proven by a filesystem snapshot, not by reading the code

"There is no `rm` in this file" is a review claim, and review claims decay. The test that
matters takes a recursive hash of the fixture tree before and after a full prune and asserts
byte-equality except for `projects.json` and `.git/worktrees/` metadata.

That test fails if a future change introduces destruction *anywhere* in the call graph,
including in a dependency — which a grep for `rm` cannot do. Per `evidence-discipline.md`,
every such test is proven to fail without the fix (`git stash` and rerun), and the `--dry-run`
zero-write claim is measured the same way: snapshot, run, compare — including `projects.json`,
which a dry run must not touch either.

### D7 — Archiving refuses to hide anything broken

`ui-quality.md`: compacting must never hide a failure. An archived project vanishes from the
overview, which is exactly a place a broken thing could sit unseen.

So archiving refuses an entry that has **open issues** or a **live sentinel/orchestrator
PID**, and reports the refusal with its reason. Combined with the overview showing an
archived count with a toggle, nothing wrong can end up hidden without being counted where the
reader is standing.

### D8 — Confirmation is the default, `--yes` is the opt-out

A bare `set-project prune` prints the plan and asks. This is the `set-project init --dry-run`
precedent: a tool with blast radius states its radius before acting.

## Risks / Trade-offs

- **A project directory is temporarily unavailable and gets deregistered** → D2's parent-
  directory check. Deregistration is also cheap to undo (`set-project init` re-registers),
  and the pre-write backup holds the previous registry.
- **`git worktree prune` races an orchestration that is creating a worktree** → the tool acts
  only on git's own `prunable` flag, computed at that moment, and never passes `--expire`,
  so a worktree being created is not a candidate. Worst case it prunes nothing.
- **Archiving hides a project someone still needs** → reversible by clearing one flag; the
  overview shows the archived count; D7 refuses to archive anything with open issues or a
  live process.
- **The overview's archived filter drifts from the CLI's notion of archived** → both read the
  same `archived` field via the same module; no second definition exists.
- **The backup files accumulate** → same pattern as the existing `harvest-state.json.bak-*`;
  small JSON, and losing a backup is not a loss of data. Not solved here.

## Migration Plan

1. Ship the code with tests; no behaviour changes until the command is invoked.
2. Run `set-project prune --dry-run` and read the plan.
3. Run `set-project prune` — deregisters the 12 dead entries, prunes the 10 orphaned worktree
   records. Verify against the pre-run backup.
4. Only then, if wanted, `set-project prune --archive-e2e-older-than 30d`.
5. **Rollback**: restore `projects.json` from its timestamped backup. Pruned worktree records
   are recreated by `git worktree add` if ever needed; the branches were never touched.

Entries written before this change have no `archived` field, and absence reads as not
archived — so no migration of existing data is required.

## Open Questions

None blocking. The archive threshold's default is deliberately absent rather than undecided
(D4).
