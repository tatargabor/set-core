## Why

The fleet screen can start an agent, but only ever in a project's main checkout: the form
sends `cwd: project.root` and nothing else, and the start endpoint refuses any directory
outside the set of known project roots. Parallel work in this framework happens in git
worktrees — that is what `set-new` and the whole change/ branch discipline exist for — so
the one place an agent is most useful to start is the one place the screen cannot start it.
Today the only route into a worktree is `set-work <id>` followed by typing `claude` in the
terminal it opens, which leaves that agent outside the framework's ownership and off the
browser terminal.

The service that actually starts agents already accepts any working directory. The
restriction lives entirely in the HTTP guard and in a hardcoded field in the form, so this
change adds a choice rather than rebuilding a mechanism.

## What Changes

- **A project's worktrees become a queryable list.** A new read endpoint answers, for one
  known project, the directories an agent could be started in: the main checkout plus each
  git worktree, each carrying its branch, whether it is the main checkout, and whether git
  reports it `prunable`.
- **`prunable` is measured and carried, which nothing here does today.** The porcelain
  parser in the API helpers ignores the `prunable` line, and `set-list` prints such
  worktrees as if they were live — measured in this repository on 2026-08-23: three of four
  listed worktrees are prunable, i.e. their directory no longer exists. A prunable worktree
  is never offered and never accepted as a start location.
- **The start guard widens by exactly one rule, not into a permissive one.** `POST
  /api/fleet/agents` accepts a `cwd` that is a known project root (unchanged), or a
  non-prunable worktree that `git worktree list` reports for one of those roots. An
  arbitrary existing directory — including an arbitrary subdirectory of a known root — is
  still refused with the same 400.
- **The start form offers the choice.** A worktree selector defaults to the main checkout,
  labels entries by branch, and is omitted entirely when a project has no other worktree,
  so single-checkout projects gain no clutter.
- **Out of scope, by the user's decision:** creating a worktree from this form. New
  worktrees stay with `set-new <id>`; one created there appears in the selector on the next
  read.

## Capabilities

### New Capabilities
- `fleet-agent-start-location`: which directories the fleet screen may start an agent in —
  how a project's startable locations are enumerated, which of them are refused and why,
  and how the surface offers the choice.

### Modified Capabilities
<!-- None. No existing spec states the start endpoint's cwd rule; agent-fleet-restore
     covers restoring recorded entries and is unaffected. -->

## Impact

- `lib/set_orch/api/fleet.py` — new worktree-listing route; `_known_roots()`-based guard in
  `fleet_start_agent` gains the worktree branch.
- `lib/set_orch/api/helpers.py` — `_list_worktrees` learns to carry `prunable` and the
  main-checkout flag. It has other callers (media, learnings, sessions), so the field is
  additive.
- `web/src/pages/Fleet.tsx` — `StartAgent` gains the selector and stops hardcoding
  `project.root`.
- `web/src/lib/api.ts` — the new endpoint's client and types.
- No change to `lib/set_orch/fleet/owner.py`: it already starts in the `cwd` it is given.
- The framework still never creates, removes or writes into a git worktree from the
  dashboard — it only reads the list and starts a process there.
