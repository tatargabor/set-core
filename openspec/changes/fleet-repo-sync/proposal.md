## Why

The owner works across a few dozen registered projects and two machines, and today the only way
to know whether every project is committed and pushed — and so whether the second machine can
pull today's state — is a hand-written shell loop over the registry. Measured on 2026-11-24: that
loop found 37 trees ahead of their upstream, several diverged, local branches never pushed, and
pushes that would have triggered a production deploy. The answer was right but lived in one
session's terminal and was gone by the next.

## What Changes

- A new fleet header chip, **Repos**, opening a floating table of every recently active
  registered project's git state: current branch, uncommitted files, ahead/behind its upstream,
  local branches with commits on no remote, worktrees (branch, age, merged or not, dirty), stash
  count, the remote's host, and when the remote refs were last fetched.
- **On demand only.** Nothing is computed until the table is opened; a refresh control recomputes.
  No polling, no background cycle. The chip shows the problem count of the LAST measurement
  together with its age, and says "not measured" before the first one — never a zero it did not
  measure.
- **Recently active** means a commit on any local branch, or a session transcript written, within
  a window — 30 days by default, adjustable in the table and in machine-local config
  (`fleet_repo_sync_days`). Archived projects and e2e-run scaffolds are left out, and the table
  says how many were left out and why.
- A separate **fetch** control runs `git fetch` across the listed projects (bounded concurrency,
  per-repo timeout), because ahead/behind is only as fresh as the remote refs; it is never run
  implicitly.
- A **push may deploy** hint per project, read from the tree's own CI and hosting files (a deploy
  job that runs on a push to the current branch without a manual gate; a linked hosting project
  whose production branch cannot be read locally). It is a hint naming its file, never a verdict.
- Problem rows sort first; the table is read-only in this round — no push, pull or delete buttons.

## Capabilities

### New Capabilities
- `fleet-repo-sync`: the on-demand, read-only view of every recently active project's commit and
  push state, its worktrees, and its push-triggers-deploy hints, reachable from the fleet header.

### Modified Capabilities
<!-- none: the header gains a chip, but no existing requirement changes -->

## Impact

- **Core (Layer 1):** a new `lib/set_orch/fleet/repo_sync.py` (git state collection, activity
  window, deploy hints — all generic: git, CI files and hosting link files, no web framework
  logic) and two routes in `lib/set_orch/api/fleet.py` (`GET /api/fleet/repo-sync`,
  `POST /api/fleet/repo-sync/fetch`).
- **Web:** `web/src/components/FleetRepoSync.tsx`, `web/src/lib/fleetRepoSync.ts`, one chip in
  `web/src/pages/Fleet.tsx`, and the rebuilt `web/dist`.
- **Config:** one machine-local key, `fleet_repo_sync_days`.
- **Confidentiality:** the view reads consumer trees at runtime and persists nothing derived from
  them; logs carry counts and project names already in the registry, never file contents or
  commit messages.
