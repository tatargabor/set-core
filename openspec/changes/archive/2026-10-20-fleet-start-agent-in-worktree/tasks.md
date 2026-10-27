## 1. The worktree list learns what it currently drops

- [x] 1.1 Extend `_list_worktrees` in `lib/set_orch/api/helpers.py` to parse the porcelain `prunable` line and carry `prunable: bool`, and to mark the first entry `is_main: true` (git always emits the main working tree first) [REQ: a-projects-startable-locations-are-enumerable]
- [x] 1.2 Unit-test the parser against porcelain fixtures: a main checkout only, a main checkout plus two worktrees, a detached-HEAD worktree (empty branch), and a `prunable` entry [REQ: a-projects-startable-locations-are-enumerable]
- [x] 1.3 Prove the `prunable` parsing is load-bearing: stash the parser change, confirm the prunable test fails, restore, confirm it passes (per the stash-and-rerun rule) [REQ: a-prunable-worktree-is-never-offered-and-never-accepted]
- [x] 1.4 Check the existing callers of `_list_worktrees` (`api/media.py`, `api/learnings.py`, and any other) still behave — the new fields are additive, so this is a read-and-confirm, not a rewrite [REQ: a-projects-startable-locations-are-enumerable]

## 2. The startable locations become queryable

- [x] 2.1 Add `GET /api/fleet/projects/{name}/worktrees` in `lib/set_orch/api/fleet.py` returning `{"root": ..., "locations": [{path, branch, is_main, prunable}]}`, resolving the project from the same list `_known_roots()` asks [REQ: a-projects-startable-locations-are-enumerable]
- [x] 2.2 Refuse an unknown project name with a 404 naming it, matching the neighbouring `projects/{name}/install` route — the resource is addressed by name here, so "not listed" is a 404, while the start endpoint's 400 stays what it is because there the directory is a *parameter* [REQ: a-projects-startable-locations-are-enumerable]
- [x] 2.3 Unit-test the endpoint: a project with worktrees, a project with none, a prunable entry present and marked, an unknown project refused [REQ: a-projects-startable-locations-are-enumerable]

## 3. The start guard accepts exactly what the screen offers

- [x] 3.1 In `fleet_start_agent`, accept a `cwd` that is a known root (unchanged) or a non-prunable worktree of one; compare with `os.path.realpath` on both sides [REQ: the-start-endpoint-accepts-a-known-root-or-one-of-its-worktrees-and-nothing-else]
- [x] 3.2 Keep the refusal for everything else — including a subdirectory of a known root that is not a worktree — with the existing 400 and message [REQ: the-start-endpoint-accepts-a-known-root-or-one-of-its-worktrees-and-nothing-else]
- [x] 3.3 Refuse a prunable worktree explicitly, with the reason in the message [REQ: a-prunable-worktree-is-never-offered-and-never-accepted]
- [x] 3.4 Unit-test the guard with the owner client stubbed: root accepted, live worktree accepted, prunable worktree refused, non-worktree subdirectory of a known root refused, unrelated directory refused — asserting in the refusal cases that the owner was never called [REQ: the-start-endpoint-accepts-a-known-root-or-one-of-its-worktrees-and-nothing-else]
- [x] 3.5 Log the accepted location and, on refusal, the reason class (root / worktree / prunable / unknown) — path only, no directory contents [REQ: the-start-endpoint-accepts-a-known-root-or-one-of-its-worktrees-and-nothing-else]

## 4. The form offers the choice

- [x] 4.1 Add the client call and types for the new endpoint in `web/src/lib/api.ts` [REQ: the-start-form-lets-the-reader-choose-the-location]
- [x] 4.2 In `StartAgent` (`web/src/pages/Fleet.tsx`), fetch the locations when the form opens, render a selector defaulting to the main checkout, and send the selected path as `cwd` instead of the hardcoded `project.root` [REQ: the-start-form-lets-the-reader-choose-the-location]
- [x] 4.3 Label each entry by branch, falling back to the directory name when the branch is empty; omit prunable entries [REQ: a-prunable-worktree-is-never-offered-and-never-accepted]
- [x] 4.4 Render no selector when the only location is the main checkout, and keep the form compact enough not to disturb the header row it lives in [REQ: the-start-form-lets-the-reader-choose-the-location]
- [x] 4.5 On a failed location read, keep the project root and say the list could not be read — never a silent empty selector [REQ: the-start-form-lets-the-reader-choose-the-location]
- [x] 4.6 Web unit tests: selector present with worktrees, absent without, prunable omitted, submitted `cwd` is the selected path, read failure still starts in the root and says so [REQ: the-start-form-lets-the-reader-choose-the-location]

## 5. Verification

- [x] 5.1 Run the Python unit suite and compare failures against a baseline built per the `regression-baseline` skill — a set diff, not a remembered count [REQ: the-start-endpoint-accepts-a-known-root-or-one-of-its-worktrees-and-nothing-else]
- [x] 5.2 Run the web unit suite and `tsc -b` in `web/` (`--noEmit` alone measures nothing here), then `pnpm build` so port 7400 serves the change [REQ: the-start-form-lets-the-reader-choose-the-location]
- [x] 5.3 **Browser visual check (required, not optional):** open the running dashboard's fleet screen with Claude in Chrome, open the start form on a project that has a live worktree, and report what is actually on screen — the selector, its default, its labels, and that the row is not crowded. If the browser cannot be reached, leave this task OPEN and say so in the commit [REQ: the-start-form-lets-the-reader-choose-the-location]
- [x] 5.4 End-to-end by hand: start an agent into a live worktree from the screen, then confirm the process's `/proc/<pid>/cwd` is that worktree — the measurement, not the form's own claim [REQ: the-start-endpoint-accepts-a-known-root-or-one-of-its-worktrees-and-nothing-else]
- [x] 5.5 Add a bug-register entry for `set-list` showing prunable worktrees as live, with the measurement from this repository — out of scope here, and losing it costs the next reader the same confusion [REQ: a-prunable-worktree-is-never-offered-and-never-accepted]

## Acceptance Criteria (from spec scenarios)

### A project's startable locations are enumerable
- [x] AC-1: WHEN the startable locations of a project whose repository has a main checkout and two worktrees are requested THEN three entries are returned, exactly one marked as the main checkout, each carrying its path and branch [REQ: a-projects-startable-locations-are-enumerable, scenario: a-project-with-worktrees-lists-all-of-them]
- [x] AC-2: WHEN the startable locations of a project with no additional worktree are requested THEN exactly one entry is returned, marked as the main checkout [REQ: a-projects-startable-locations-are-enumerable, scenario: a-project-with-no-worktrees-lists-only-its-main-checkout]
- [x] AC-3: WHEN git reports a worktree as prunable THEN the entry is present and carries `prunable: true` [REQ: a-projects-startable-locations-are-enumerable, scenario: a-prunable-worktree-is-reported-as-prunable-rather-than-omitted]
- [x] AC-4: WHEN startable locations are requested for a project name this screen does not list THEN the request is refused with a 404 naming it, and no list is returned [REQ: a-projects-startable-locations-are-enumerable, scenario: a-project-that-is-not-known-is-refused]

### A prunable worktree is never offered and never accepted
- [x] AC-5: WHEN the start form renders for a project with one live and one prunable worktree THEN the selector offers the main checkout and the live worktree only [REQ: a-prunable-worktree-is-never-offered-and-never-accepted, scenario: the-selector-omits-a-prunable-worktree]
- [x] AC-6: WHEN a start is requested with a prunable worktree's path THEN it is refused with a 400 and no agent is started [REQ: a-prunable-worktree-is-never-offered-and-never-accepted, scenario: starting-in-a-prunable-worktree-is-refused]

### The start endpoint accepts a known root or one of its worktrees, and nothing else
- [x] AC-7: WHEN a start is requested with a registered project's root as `cwd` THEN the owner service is asked to start an agent there [REQ: the-start-endpoint-accepts-a-known-root-or-one-of-its-worktrees-and-nothing-else, scenario: a-known-project-root-is-still-accepted]
- [x] AC-8: WHEN a start is requested with a live worktree of a known project THEN the owner service is asked to start an agent in that worktree [REQ: the-start-endpoint-accepts-a-known-root-or-one-of-its-worktrees-and-nothing-else, scenario: a-worktree-of-a-known-project-is-accepted]
- [x] AC-9: WHEN a start is requested with a directory inside a known root that is not one of its worktrees THEN it is refused with a 400 and the owner is not asked [REQ: the-start-endpoint-accepts-a-known-root-or-one-of-its-worktrees-and-nothing-else, scenario: an-arbitrary-subdirectory-of-a-known-project-is-refused]
- [x] AC-10: WHEN a start is requested with an existing directory outside every known root and worktree THEN it is refused with a 400 and the owner is not asked [REQ: the-start-endpoint-accepts-a-known-root-or-one-of-its-worktrees-and-nothing-else, scenario: a-directory-belonging-to-no-known-project-is-refused]

### The start form lets the reader choose the location
- [x] AC-11: WHEN the start form is opened for a project with at least one live worktree THEN a location selector is shown with the main checkout selected [REQ: the-start-form-lets-the-reader-choose-the-location, scenario: a-project-with-worktrees-offers-a-choice-defaulting-to-the-main-checkout]
- [x] AC-12: WHEN the reader selects a worktree and submits THEN the start request carries that worktree's path as `cwd` [REQ: the-start-form-lets-the-reader-choose-the-location, scenario: the-chosen-worktree-is-what-the-start-requests]
- [x] AC-13: WHEN the start form is opened for a project whose only location is its main checkout THEN no selector is rendered and the request carries the project root [REQ: the-start-form-lets-the-reader-choose-the-location, scenario: a-single-checkout-project-shows-no-selector]
- [x] AC-14: WHEN the startable locations cannot be read THEN the form still starts an agent in the project root and says the worktree list could not be read [REQ: the-start-form-lets-the-reader-choose-the-location, scenario: the-locations-being-unreadable-does-not-remove-the-ability-to-start]
