## 1. Collection core (Layer 1: `lib/set_orch/fleet/repo_sync.py`)

- [x] 1.1 Registry walk with the activity window (first commits + transcripts; narrowed to commits by 5.1), `days` from request → `fleet_repo_sync_days` → 30; `excluded` counts for archived, e2e-run, inactive and missing [REQ: the-listed-projects-are-the-recently-active-registered-ones]
- [x] 1.2 Per-project git state: branch/detached, uncommitted count, upstream + ahead/behind or `no-upstream`, diverged flag, stash count, remote host without credentials, fetch age from `FETCH_HEAD`; every git call timed out at 10 s with `GIT_TERMINAL_PROMPT=0` and `GIT_OPTIONAL_LOCKS=0`, a failure is `null` + reason [REQ: each-project-row-carries-its-commit-and-push-state]
- [x] 1.3 Unpushed local branches: every local branch with commits on no remote ref, with count and last commit age [REQ: each-project-row-carries-its-commit-and-push-state]
- [x] 1.4 Worktrees: path, branch, last commit age, uncommitted count, `merged` into the main worktree's branch, `missing` directory [REQ: worktrees-are-listed-with-what-decides-whether-they-are-worth-keeping]
- [x] 1.5 Deploy hint (D5): GitLab rules/only/when, GitHub push workflows with a production environment or deploy job, hosting link files → `yes | no | unknown` with the source file [REQ: a-push-that-may-deploy-is-hinted-naming-its-source]
- [x] 1.6 Problem classification per row and problem-first ordering; 8-worker pool; `duration_ms` in the answer [REQ: the-chip-never-shows-a-calm-it-did-not-measure]
- [x] 1.7 Explicit fetch: `git fetch --all --prune`, 4 workers, 30 s timeout, ssh `BatchMode=yes`, per-project `ok | timeout | failed` [REQ: fetching-is-explicit-and-bounded]
- [x] 1.8 Logging per D7: counts and registered names only, never branch names, in-tree paths, messages or URLs; no file written by a scan [REQ: nothing-read-from-a-project-is-persisted]

## 2. API (Layer 1: `lib/set_orch/api/fleet.py`)

- [x] 2.1 `GET /api/fleet/repo-sync?days=` returning the collection; not called by any existing route or cycle [REQ: the-state-is-computed-only-when-somebody-asks-for-it]
- [x] 2.2 `POST /api/fleet/repo-sync/fetch` with an optional project list [REQ: fetching-is-explicit-and-bounded]

## 3. Screen (web)

- [x] 3.1 `web/src/lib/fleetRepoSync.ts`: parse the answer, problem labels, chip text ("not measured" / count + age) [REQ: the-chip-never-shows-a-calm-it-did-not-measure]
- [x] 3.2 `web/src/components/FleetRepoSync.tsx`: header chip; the request is sent on open and on refresh only [REQ: the-state-is-computed-only-when-somebody-asks-for-it]
- [x] 3.3 Floating table: one row per project, problem rows first, expandable branches/worktrees, deploy hint with its file, window selector, fetch control; closes on its control, Escape, outside click; no write control besides fetch [REQ: the-table-floats-and-is-read-only]
- [x] 3.4 Mount the chip in `web/src/pages/Fleet.tsx` beside the other header chips [REQ: the-table-floats-and-is-read-only]
- [x] 3.5 Rebuild `web/dist` [REQ: the-table-floats-and-is-read-only]

## 5. Owner's follow-up (2026-11-24): commit-only activity, hiding

- [x] 5.1 Activity from commits only, local and remote-tracking branches; the transcript source removed [REQ: the-listed-projects-are-the-recently-active-registered-ones]
- [x] 5.2 `fleet_repo_sync_hidden` list, `excluded.hidden`, `hidden` in the answer, `POST /api/fleet/repo-sync/hidden` [REQ: the-owner-can-hide-a-project-and-bring-it-back]
- [x] 5.3 Hide control per row and a separate hidden view with restore [REQ: the-owner-can-hide-a-project-and-bring-it-back]
- [x] 5.4 Tests for both, and a browser look at the hidden view [REQ: the-owner-can-hide-a-project-and-bring-it-back]

## 4. Tests and verification

- [x] 4.1 Unit tests over throwaway git repos: ahead/behind/diverged, no upstream, unpushed branch, merged and missing worktree, a failing git call is a `null` gap, activity window by commit and by transcript, exclusions counted [REQ: each-project-row-carries-its-commit-and-push-state]
- [x] 4.2 Unit tests for the deploy hint: automatic production job → yes, manual gate → not yes, hosting link only → unknown, unparseable CI → unknown [REQ: a-push-that-may-deploy-is-hinted-naming-its-source]
- [x] 4.3 Web unit tests for the parser and chip text, including "not measured" before the first answer [REQ: the-chip-never-shows-a-calm-it-did-not-measure]
- [x] 4.4 Live run against this machine's registry: the answer agrees with a hand loop on at least five projects (ahead/behind, dirty, deploy hint) [REQ: each-project-row-carries-its-commit-and-push-state]
- [x] 4.5 Visual check in the browser (Claude in Chrome): chip before and after opening, the table floats without moving the header, problem rows first, a deploy hint readable [REQ: the-table-floats-and-is-read-only]
- [x] 4.6 `openspec validate --strict`, `/opsx:verify` with `templates/core/rules/spec-verify-gate.md` [REQ: the-state-is-computed-only-when-somebody-asks-for-it]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN the fleet loads and the Repos table is not opened THEN no repo-sync request is sent and no git command runs for it [REQ: the-state-is-computed-only-when-somebody-asks-for-it, scenario: opening-the-fleet-does-not-scan]
- [x] AC-2: WHEN the owner opens the Repos table THEN exactly one request is sent, a second only on refresh [REQ: the-state-is-computed-only-when-somebody-asks-for-it, scenario: opening-the-table-scans-once]
- [x] AC-3: WHEN a project's newest commit and transcript are older than the window THEN it is not listed and `excluded.inactive` counts it [REQ: the-listed-projects-are-the-recently-active-registered-ones, scenario: an-old-project-is-left-out-and-counted]
- [x] AC-4: WHEN the only recent commit is another author's on a remote-tracking branch THEN the project is listed [REQ: the-listed-projects-are-the-recently-active-registered-ones, scenario: a-commit-somebody-else-pushed-makes-a-project-active]
- [x] AC-4b: WHEN only a session transcript is recent THEN the project is not listed [REQ: the-listed-projects-are-the-recently-active-registered-ones, scenario: session-activity-alone-does-not-list-a-project]
- [x] AC-19: WHEN a project is hidden THEN it is not listed, counted in `excluded.hidden`, shown in the hidden view [REQ: the-owner-can-hide-a-project-and-bring-it-back, scenario: a-hidden-project-leaves-the-table-and-appears-in-the-hidden-view]
- [x] AC-20: WHEN a hidden project is restored THEN it is listed again [REQ: the-owner-can-hide-a-project-and-bring-it-back, scenario: a-restored-project-returns]
- [x] AC-5: WHEN a registered project's path does not exist THEN it is counted in `excluded.missing` with its name [REQ: the-listed-projects-are-the-recently-active-registered-ones, scenario: a-missing-tree-is-reported-not-dropped]
- [x] AC-6: WHEN the branch is 2 ahead and 3 behind THEN the row says so and is flagged diverged [REQ: each-project-row-carries-its-commit-and-push-state, scenario: ahead-and-behind-are-counted-against-the-upstream]
- [x] AC-7: WHEN another local branch has 4 commits on no remote THEN it is listed with count 4 [REQ: each-project-row-carries-its-commit-and-push-state, scenario: a-branch-with-no-remote-copy-is-listed]
- [x] AC-8: WHEN a git command fails or times out THEN the fields are `null` with a reason and the row is a problem [REQ: each-project-row-carries-its-commit-and-push-state, scenario: an-unreadable-repository-is-a-gap-not-a-clean-row]
- [x] AC-9: WHEN a worktree's branch is merged and clean THEN it is marked `merged` and clean [REQ: worktrees-are-listed-with-what-decides-whether-they-are-worth-keeping, scenario: a-merged-clean-worktree-is-marked-removable]
- [x] AC-10: WHEN a listed worktree's path is gone THEN it is marked `missing` [REQ: worktrees-are-listed-with-what-decides-whether-they-are-worth-keeping, scenario: a-worktree-whose-directory-is-gone-is-marked-prunable]
- [x] AC-11: WHEN an automatic production deploy job runs on the current branch THEN `push_may_deploy: yes` with the file [REQ: a-push-that-may-deploy-is-hinted-naming-its-source, scenario: an-automatic-production-deploy-on-the-current-branch-is-hinted]
- [x] AC-12: WHEN the only production job is `when: manual` THEN not `yes` [REQ: a-push-that-may-deploy-is-hinted-naming-its-source, scenario: a-manual-production-gate-is-not-a-deploy-on-push]
- [x] AC-13: WHEN only a hosting link file exists THEN `unknown` naming it [REQ: a-push-that-may-deploy-is-hinted-naming-its-source, scenario: a-linked-hosting-project-is-unknown-not-safe]
- [x] AC-14: WHEN one remote times out THEN it is `timeout` and the others are still returned [REQ: fetching-is-explicit-and-bounded, scenario: a-slow-remote-does-not-hold-the-others]
- [x] AC-15: WHEN the table has not been opened THEN the chip reads "not measured" with no count [REQ: the-chip-never-shows-a-calm-it-did-not-measure, scenario: before-the-first-opening-the-chip-makes-no-claim]
- [x] AC-16: WHEN a measurement found 5 problems 10 minutes ago THEN the chip shows 5 and its age [REQ: the-chip-never-shows-a-calm-it-did-not-measure, scenario: after-a-measurement-the-chip-carries-its-count-and-age]
- [x] AC-17: WHEN the table opens THEN the header height and agent area position are unchanged [REQ: the-table-floats-and-is-read-only, scenario: opening-the-table-moves-nothing]
- [x] AC-18: WHEN a scan completes THEN no file under the set-core state or cache directories changed because of it [REQ: nothing-read-from-a-project-is-persisted, scenario: a-scan-leaves-no-derived-file]
