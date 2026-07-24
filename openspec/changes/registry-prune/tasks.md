## 1. The prune module (Layer 1, domain-free)

- [ ] 1.1 Create `lib/set_orch/registry_prune.py` with module logger, and a `PruneReport`
      dataclass holding `deregistered`, `unreachable`, `archived`, `archive_refused`,
      `worktrees_pruned` — so callers read a structure, not parsed prose [REQ: the-prune-never-removes-anything-from-disk]
- [ ] 1.2 Implement `classify_entries(projects)` → deregistrable / unreachable / kept, keyed
      solely on `isdir(path)` and `isdir(parent)`. No age, no emptiness, no name matching [REQ: deregistration-requires-the-directory-to-be-absent]
- [ ] 1.3 Implement the unreachable branch: path absent AND parent absent → keep, report
      separately [REQ: an-unreachable-path-is-reported-not-deregistered]
- [ ] 1.4 Implement `prunable_worktrees(project_path)` — parse `git worktree list --porcelain`
      and return only records carrying git's own `prunable` flag; empty list ⇒ caller skips
      the repo entirely [REQ: only-git-flagged-prunable-worktree-records-are-pruned]
- [ ] 1.5 Implement `prune_worktrees(project_path)` calling `git worktree prune` with no
      `--expire`; add a unit-level guard asserting the argv contains neither `remove` nor
      `--expire` nor `-D` [REQ: only-git-flagged-prunable-worktree-records-are-pruned]
- [ ] 1.6 Implement `archive_candidates(projects, threshold, e2e_root)` requiring BOTH the
      explicit threshold and the E2E-root location; no default threshold anywhere in the
      signature or the CLI [REQ: archiving-requires-both-an-explicit-threshold-and-the-e2e-location]
- [ ] 1.7 Implement the archive refusal check: open issues (`.set/issues/registry.json`) or a
      live sentinel/orchestrator PID ⇒ refuse with a reason string [REQ: archiving-refuses-to-hide-a-project-in-a-broken-or-running-state]
- [ ] 1.8 Implement `apply_archive(entry)` setting `archived: true` + `archivedAt`, leaving
      every other field intact, and `clear_archive(entry)` as its exact inverse [REQ: archiving-marks-an-entry-without-removing-it]
- [ ] 1.9 Implement `backup_registry()` writing `projects.json.bak-<unix-ts>` and raising on
      failure, called before any registry mutation [REQ: the-registry-is-backed-up-before-it-is-written]
- [ ] 1.10 Implement `run_prune(..., preview: bool)` orchestrating the above; in preview mode
      it takes no write path at all — not the backup, not the registry, not git [REQ: preview-mode-writes-nothing]

## 2. Registry plumbing

- [ ] 2.1 Extend `_load_projects()` in `lib/set_orch/api/helpers.py` to carry the `archived` /
      `archivedAt` fields through (absent ⇒ not archived), and confirm `_save_projects()`
      round-trips them [REQ: archiving-marks-an-entry-without-removing-it]
- [ ] 2.2 Filter archived entries out of `list_projects()` in `lib/set_orch/api/projects.py`,
      add `include_archived: bool = False`, and include an `archived_count` in the response so
      the omission is never silent [REQ: project-endpoints]

## 3. CLI surface

- [ ] 3.1 Add the `prune` subcommand to `bin/set-project` — dispatch `case` (~:1427) and
      `usage()` (~:683) — with `--dry-run`, `--archive-e2e-older-than <Nd>`, `--yes` [REQ: a-mutating-prune-confirms-before-acting]
- [ ] 3.2 Print the plan (deregister / unreachable / archive / refused / worktrees) and prompt
      for confirmation; `--yes` skips it, `--dry-run` never prompts because it never writes [REQ: a-mutating-prune-confirms-before-acting]

## 4. Dashboard

- [ ] 4.1 Drop archived projects from the overview list in
      `web/src/hooks/useProjectOverview.ts` / `web/src/pages/Manager.tsx` [REQ: project-endpoints]
- [ ] 4.2 Show the archived count next to the list with a toggle to reveal them — hidden must
      stay counted where the reader is standing (`ui-quality.md`) [REQ: project-endpoints]

## 5. Proof, per evidence-discipline.md

- [ ] 5.1 `tests/unit/test_registry_prune_loss_free.py` — recursive content hash of a fixture
      tree before/after a full prune; equal except `projects.json` and `.git/worktrees/` [REQ: the-prune-never-removes-anything-from-disk]
- [ ] 5.2 Test that a branch behind a pruned orphan still exists at the same SHA [REQ: the-prune-never-removes-anything-from-disk]
- [ ] 5.3 Test the live-directory invariant: an existing directory is never deregistered,
      including an empty one and a 200-day-old one [REQ: deregistration-requires-the-directory-to-be-absent]
- [ ] 5.4 Test the unreachable branch with a missing parent [REQ: an-unreachable-path-is-reported-not-deregistered]
- [ ] 5.5 Test that a live worktree's directory and record survive, and that a repo with zero
      prunable records is not invoked on at all (assert the git call did not happen) [REQ: only-git-flagged-prunable-worktree-records-are-pruned]
- [ ] 5.6 Test archive reversibility: archive → clear ⇒ entry byte-equivalent to the original [REQ: archiving-marks-an-entry-without-removing-it]
- [ ] 5.7 Test that a bare prune archives nothing; that an old non-E2E project is not
      archived; that a recent E2E run is not archived [REQ: archiving-requires-both-an-explicit-threshold-and-the-e2e-location]
- [ ] 5.8 Test both archive refusals (open issue, live PID), asserting the reason is reported [REQ: archiving-refuses-to-hide-a-project-in-a-broken-or-running-state]
- [ ] 5.9 Test preview writes nothing — assert registry content AND mtime unchanged, and that
      no `.bak-` file appeared [REQ: preview-mode-writes-nothing]
- [ ] 5.10 Test the backup exists with pre-prune content, and that an unwritable backup aborts
      before mutating [REQ: the-registry-is-backed-up-before-it-is-written]
- [ ] 5.11 Test that declining confirmation writes nothing, and that `--yes` proceeds [REQ: a-mutating-prune-confirms-before-acting]
- [ ] 5.12 **Prove every test above fails without the fix**: `git stash && pytest <files>;
      git stash pop`, and record which ones passed either way (those measure nothing and get
      rewritten). Restore is verified by re-reading the file, not assumed [REQ: the-prune-never-removes-anything-from-disk]

## 6. Live run against the real registry

- [ ] 6.1 `set-project prune --dry-run` — plan names the 12 dead entries and the 10 orphaned
      worktree records, and a before/after sha256 of `projects.json` is identical [REQ: preview-mode-writes-nothing]
- [ ] 6.2 `set-project prune` for real; verify the backup, diff it against the new registry,
      and confirm all 38 live-directory entries are still present [REQ: deregistration-requires-the-directory-to-be-absent]
- [ ] 6.3 Confirm the 10 `change/*` branches still exist at their pre-prune SHAs (captured
      before step 6.2) [REQ: the-prune-never-removes-anything-from-disk]
- [ ] 6.4 Regression check against a `HEAD` baseline worktree with `PYTHONPATH` set to the
      baseline's three source roots and the session-end leak assertion — diff the failure sets,
      not the counts [REQ: the-prune-never-removes-anything-from-disk]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN a prune runs to completion over a fixture with live worktrees and orphaned
      records THEN the recursive tree hash is unchanged except the registry and
      `.git/worktrees/` [REQ: the-prune-never-removes-anything-from-disk, scenario: a-full-prune-leaves-the-tree-byte-identical]
- [ ] AC-2: WHEN an orphaned worktree record for `change/x` is pruned THEN `change/x` still
      exists at the same commit [REQ: the-prune-never-removes-anything-from-disk, scenario: a-branch-behind-an-orphaned-worktree-survives]
- [ ] AC-3: WHEN a registered entry's path is an existing directory, however old or empty
      THEN the entry remains [REQ: deregistration-requires-the-directory-to-be-absent, scenario: a-live-directory-is-never-deregistered]
- [ ] AC-4: WHEN a path is absent and its parent exists THEN the entry is removed [REQ: deregistration-requires-the-directory-to-be-absent, scenario: a-deleted-directory-is-deregistered]
- [ ] AC-5: WHEN an entry points at `/mnt/nas/proj` and `/mnt/nas` is absent THEN the entry is
      kept and reported unreachable [REQ: an-unreachable-path-is-reported-not-deregistered, scenario: an-unmounted-filesystem]
- [ ] AC-6: WHEN a project has a worktree whose directory exists THEN the record and directory
      are unchanged [REQ: only-git-flagged-prunable-worktree-records-are-pruned, scenario: a-live-worktree-is-untouched]
- [ ] AC-7: WHEN a project has no prunable records THEN no git mutation is attempted [REQ: only-git-flagged-prunable-worktree-records-are-pruned, scenario: no-prunable-records]
- [ ] AC-8: WHEN an entry is archived then un-archived THEN it is byte-equivalent to its
      pre-archive state [REQ: archiving-marks-an-entry-without-removing-it, scenario: archive-is-reversible]
- [ ] AC-9: WHEN an entry is archived THEN it is still present in the registry file [REQ: archiving-marks-an-entry-without-removing-it, scenario: archiving-does-not-deregister]
- [ ] AC-10: WHEN the prune runs without an archive threshold THEN no entry gains an
      `archived` field [REQ: archiving-requires-both-an-explicit-threshold-and-the-e2e-location, scenario: a-bare-prune-archives-nothing]
- [ ] AC-11: WHEN a project outside the E2E root is older than the threshold THEN it is not
      archived [REQ: archiving-requires-both-an-explicit-threshold-and-the-e2e-location, scenario: an-old-project-outside-the-e2e-root]
- [ ] AC-12: WHEN an E2E entry is newer than the threshold THEN it is not archived [REQ: archiving-requires-both-an-explicit-threshold-and-the-e2e-location, scenario: a-recent-e2e-run]
- [ ] AC-13: WHEN an eligible entry has an open issue THEN it is not archived and the refusal
      names the count [REQ: archiving-refuses-to-hide-a-project-in-a-broken-or-running-state, scenario: open-issues-block-archiving]
- [ ] AC-14: WHEN an eligible entry has a live sentinel or orchestrator PID THEN it is not
      archived and the refusal names the process [REQ: archiving-refuses-to-hide-a-project-in-a-broken-or-running-state, scenario: a-live-process-blocks-archiving]
- [ ] AC-15: WHEN the prune runs in preview mode THEN the registry's content and mtime are
      unchanged [REQ: preview-mode-writes-nothing, scenario: a-preview-leaves-the-registry-untouched]
- [ ] AC-16: WHEN a prune deregisters at least one entry THEN a timestamped backup holding the
      pre-prune content exists [REQ: the-registry-is-backed-up-before-it-is-written, scenario: backup-precedes-mutation]
- [ ] AC-17: WHEN the backup cannot be written THEN the registry is unchanged and the failure
      is reported [REQ: the-registry-is-backed-up-before-it-is-written, scenario: an-unwritable-backup-aborts]
- [ ] AC-18: WHEN the operator declines at the prompt THEN nothing is written [REQ: a-mutating-prune-confirms-before-acting, scenario: declining-the-confirmation]
- [ ] AC-19: WHEN the operator passes assume-yes THEN the prune proceeds without prompting [REQ: a-mutating-prune-confirms-before-acting, scenario: assume-yes-skips-the-prompt]
- [ ] AC-20: WHEN GET /api/projects is called THEN non-archived projects are returned with
      status and issue counts [REQ: project-endpoints, scenario: list-projects-with-status]
- [ ] AC-21: WHEN GET /api/projects is called and entries are archived THEN they are absent
      and the response reports the omitted count [REQ: project-endpoints, scenario: archived-projects-are-omitted-but-counted]
- [ ] AC-22: WHEN GET /api/projects?include_archived=true is called THEN archived entries are
      returned, each marked archived [REQ: project-endpoints, scenario: archived-projects-on-request]
- [ ] AC-23: WHEN POST /api/projects is called with name, path, mode THEN the project is added
      and a sentinel can start [REQ: project-endpoints, scenario: register-project]
