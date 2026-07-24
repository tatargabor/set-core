## 1. The named archive path

- [x] 1.1 Implement `archive_by_name(names, *, undo=False, preview=False, registry_file=None)`
      in `lib/set_orch/registry_prune.py`, returning a report structure (archived, unarchived,
      refused-with-reason, no-ops, default_cleared) [REQ: named-entries-can-be-archived-regardless-of-age-or-location]
- [x] 1.2 Validate every supplied name against the registry FIRST; if any is unknown, return
      without touching anything and report the unknown names [REQ: an-unknown-name-aborts-before-any-write]
- [x] 1.3 Refuse a live sentinel/orchestrator PID (`_live_process`) with no override, and
      refuse a missing directory pointing at `set-project prune` [REQ: named-archiving-refuses-a-live-process-and-a-missing-directory]
- [x] 1.4 Report the open-issue count (`_open_issue_count`) as a warning and proceed — do NOT
      reuse the bulk path's refusal here [REQ: named-archiving-warns-about-open-issues-but-proceeds]
- [x] 1.5 Apply `apply_archive()` / `clear_archive()`; unarchiving a non-archived entry is a
      reported no-op, not an error [REQ: unarchiving-restores-an-entry-exactly]
- [x] 1.6 Clear the `default` pointer when an archived name is the default, and surface it in
      the report so the caller can print it [REQ: archiving-the-default-project-clears-and-reports-the-default]
- [x] 1.7 `backup_registry()` before the first mutation; preview mode takes no write path at
      all, including no backup [REQ: named-archiving-previews-and-backs-up-like-the-bulk-path]

## 2. CLI surface

- [x] 2.1 Add `cmd_archive` / `cmd_unarchive` to `bin/set-project`, delegating to the module
      exactly as `cmd_prune` does, plus dispatch `case` entries [REQ: named-entries-can-be-archived-regardless-of-age-or-location]
- [x] 2.2 Document both in `usage()` with `--dry-run`, and state in one line that archiving
      never deletes anything [REQ: named-archiving-previews-and-backs-up-like-the-bulk-path]

## 3. Proof, per evidence-discipline.md

- [x] 3.1 `tests/unit/test_registry_archive_by_name.py` — an entry outside the E2E root and a
      recent entry are both archivable by name [REQ: named-entries-can-be-archived-regardless-of-age-or-location]
- [x] 3.2 Open issues warn and DO NOT block on the named path [REQ: named-archiving-warns-about-open-issues-but-proceeds]
- [x] 3.3 The bulk path still refuses the same entry — the two paths asserted separately, since
      a test that refused both would kill the feature and one that allowed both would make the
      dashboard lie [REQ: named-archiving-warns-about-open-issues-but-proceeds]
- [x] 3.4 A live PID refuses; a missing directory refuses and names the other command [REQ: named-archiving-refuses-a-live-process-and-a-missing-directory]
- [x] 3.5 Unknown name among several ⇒ registry byte-identical afterwards, unknown reported [REQ: an-unknown-name-aborts-before-any-write]
- [x] 3.6 Round trip: archive → unarchive ⇒ entry byte-equivalent to the original; unarchiving
      a non-archived entry is a reported no-op [REQ: unarchiving-restores-an-entry-exactly]
- [x] 3.7 Archiving the default clears it AND the report says so [REQ: archiving-the-default-project-clears-and-reports-the-default]
- [x] 3.8 Preview: content, mtime and absence of `.bak-` all asserted; backup holds pre-command
      content on a real run [REQ: named-archiving-previews-and-backs-up-like-the-bulk-path]
- [x] 3.9 **Mutation-test every decision above** with `PYTHONDONTWRITEBYTECODE=1` and a
      `__pycache__` purge before each run — without it two same-sized mutants inside one second
      share a `.pyc` and the loop blames the test instead of the code (measured today; see
      `.claude/rules/evidence-discipline.md`). Verify each restore by re-reading the file [REQ: an-unknown-name-aborts-before-any-write]

## 4. Live run

- [x] 4.1 `set-project archive --dry-run` on the four remaining E2E runs; sha256 of the
      registry identical before/after, no `.bak-` written [REQ: named-archiving-previews-and-backs-up-like-the-bulk-path]
- [x] 4.2 Run for real; confirm the default was cleared and reported, the four directories are
      untouched on disk, and the sidebar issue total is unchanged — proving nothing was hidden
      from the failure count [REQ: archiving-the-default-project-clears-and-reports-the-default]
- [x] 4.3 Regression diff against a `HEAD` baseline worktree with isolated import roots [REQ: named-entries-can-be-archived-regardless-of-age-or-location]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN an operator names a project outside the E2E run root THEN it is archived [REQ: named-entries-can-be-archived-regardless-of-age-or-location, scenario: a-project-outside-the-e2e-root-named-explicitly]
- [x] AC-2: WHEN an operator names an entry younger than any bulk threshold THEN it is archived [REQ: named-entries-can-be-archived-regardless-of-age-or-location, scenario: a-recent-entry-named-explicitly]
- [x] AC-3: WHEN an operator names an entry with open issues THEN it is archived and the count
      is stated [REQ: named-archiving-warns-about-open-issues-but-proceeds, scenario: named-entry-with-open-issues]
- [x] AC-4: WHEN bulk archiving meets an eligible entry with open issues THEN it still refuses [REQ: named-archiving-warns-about-open-issues-but-proceeds, scenario: the-bulk-path-still-refuses]
- [x] AC-5: WHEN an operator names an entry with a live PID THEN it is refused and the process
      is named [REQ: named-archiving-refuses-a-live-process-and-a-missing-directory, scenario: a-running-project]
- [x] AC-6: WHEN an operator names an entry whose directory is gone THEN it is refused and
      deregistration is suggested [REQ: named-archiving-refuses-a-live-process-and-a-missing-directory, scenario: an-entry-whose-directory-is-gone]
- [x] AC-7: WHEN three names are given and one does not exist THEN nothing is modified and the
      unknown name is reported [REQ: an-unknown-name-aborts-before-any-write, scenario: one-name-of-several-is-misspelled]
- [x] AC-8: WHEN an entry is archived by name and then unarchived THEN it is byte-equivalent to
      its pre-archive state [REQ: unarchiving-restores-an-entry-exactly, scenario: round-trip]
- [x] AC-9: WHEN an operator unarchives an entry that is not archived THEN it is unchanged and
      the no-op is reported [REQ: unarchiving-restores-an-entry-exactly, scenario: unarchiving-an-entry-that-is-not-archived]
- [x] AC-10: WHEN an operator archives the default entry THEN the default is cleared and the
      output says so and names it [REQ: archiving-the-default-project-clears-and-reports-the-default, scenario: the-default-is-archived]
- [x] AC-11: WHEN the named archive command runs in preview THEN content and mtime are
      unchanged and no backup appears [REQ: named-archiving-previews-and-backs-up-like-the-bulk-path, scenario: preview-writes-nothing]
- [x] AC-12: WHEN the named archive command modifies the registry THEN a timestamped backup
      with the pre-command content exists [REQ: named-archiving-previews-and-backs-up-like-the-bulk-path, scenario: backup-precedes-mutation]
