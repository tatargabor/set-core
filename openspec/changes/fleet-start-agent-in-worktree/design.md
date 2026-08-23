## Context

Three pieces decide today where a fleet-started agent runs, and only the last one is
actually restrictive:

- `AgentOwner.start(..., cwd=...)` (`lib/set_orch/fleet/owner.py`) `chdir`s into whatever
  directory it is given before `exec`ing the agent under a systemd scope. No constraint.
- `POST /api/fleet/agents` (`lib/set_orch/api/fleet.py`) refuses any `cwd` outside
  `_known_roots()`. That function deliberately *asks the project list* rather than
  rebuilding it, after a measured defect where a second definition of "what this screen
  knows" drifted from the first (2026-08-19: 49 projects served, 39 roots known, 10 starts
  refused on projects the screen was offering a start control for).
- `StartAgent` in `web/src/pages/Fleet.tsx` sends `cwd: project.root` and offers nothing
  else.

So a worktree — the directory this framework's whole parallel-work discipline puts agents
in — is unreachable from the screen, while the mechanism underneath is indifferent to it.

The worktree list itself is already parsed in `_list_worktrees` (`lib/set_orch/api/helpers.py`)
from `git worktree list --porcelain`, for the read-only Worktrees page. It handles the
`worktree`, `HEAD`, `branch` and `bare` lines and **drops `prunable`** — a worktree whose
directory no longer exists parses identically to a live one. Measured in this repository on
2026-08-23: `git worktree list` reports four entries, three of them `prunable`, and both the
Worktrees page and `set-list` present all four as if they were live.

## Goals / Non-Goals

**Goals:**
- A reader can choose, on the start form, which of a project's checkouts the new agent runs in.
- The endpoint accepts exactly the locations the screen offers — no more.
- A location that cannot host a process (`prunable`) is neither offered nor accepted.

**Non-Goals:**
- Creating, removing or pruning worktrees from the dashboard. `set-new` / `set-close` keep that,
  and the dashboard continues to never write into a git tree.
- Any change to how an agent is started once a directory is chosen, or to session restore.
- Fixing `set-list`'s own prunable blindness. It is the same measurement, but a CLI change with
  its own callers; it belongs in the bug register, not smuggled in here.

## Decisions

### The guard extends by asking the same list, one level deeper

`_known_roots()` stays as it is, and the start guard becomes: accept if `cwd` is a known
root, **or** if `cwd` appears in the worktree list of some known root and is not prunable.
The worktree lookup is derived from the same project list at request time, so a fourth
project source cannot reintroduce the 2026-08-19 divergence.

*Alternative rejected — fold the worktrees into `_known_roots()` itself.* That set is also
used to decide which projects the screen shows; adding worktrees to it would make each
worktree look like a project. Two meanings in one set is exactly the drift this codebase
already paid for.

*Alternative rejected — accept any path under a known root.* It reads as a small
loosening and is not: `~/code2/set-core/node_modules` would become a valid place to run an
agent, and the guard would no longer match what the form offers. The rule is membership in
an enumerated list, never a prefix test. Worktrees commonly live *outside* the root anyway
(`set-new` puts them in `../<project>-<id>/`), so a prefix test would be both too wide and
too narrow.

### `prunable` is carried, not filtered, at the parsing layer

`_list_worktrees` gains `prunable: bool` and `is_main: bool`; the filtering happens where the
decision is (the selector, the guard). Two reasons. A filter downstream of a source looks
exactly like a source that returned nothing — a defect class this repo has a name for — and
the Worktrees page should eventually *show* prunable entries as prunable rather than as
live. `is_main` comes from the first porcelain entry, which git always emits for the main
working tree, not from comparing paths to the project root.

### The list is its own read endpoint, keyed by project root

`GET /api/fleet/projects/{name}/worktrees` sits beside the existing
`POST /api/fleet/projects/{name}/install`, so the fleet screen keeps asking fleet routes and
does not have to resolve a project through the other API's `{project}` path convention. It
returns `{"root": ..., "locations": [...]}` and refuses an unknown project with the same 400
the start does.

*Alternative rejected — put the locations inside `GET /api/fleet/agents`.* That response is
polled and already large; a `git worktree list` per project on every poll is a cost paid by
every reader for a control almost nobody has open. The form asks when it opens.

### The form degrades to today's behaviour, never to a dead control

If the location list cannot be read, the form keeps the project root and says the list was
unreadable. A start control that disappears because an auxiliary read failed would be a
regression caused by a feature — and silence would read as "this project has no worktrees",
which is a false absence.

## Risks / Trade-offs

- **A `git` invocation on the start path** → one `git worktree list --porcelain` per
  refused-or-accepted start, already bounded by a 5 s timeout in the existing helper. A
  start is a deliberate, rare act; the poll path is untouched.
- **A worktree list that changed between opening the form and submitting** → the guard
  re-reads at request time, so the outcome is a 400 naming the directory rather than an
  agent in a directory that has gone. Correct, and the message says which one.
- **`realpath` mismatch between the list and the submitted path** → both sides normalise
  with `os.path.realpath` before comparing, the same way the current guard does. Worth
  naming because `/tmp` is a symlink on some systems and the worktrees measured here live
  under `/tmp`.
- **Two agents started in the same worktree** → possible, and not newly so; the same is
  already true of a project root. Out of scope here, and the label collision the owner
  already refuses covers the common case.
