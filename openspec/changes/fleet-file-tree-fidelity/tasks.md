## 1. Path fidelity in the listing (the defect nobody reported)

- [x] 1.1 Read `git ls-files` with `-z` in `_git_files` and split on NUL, dropping the trailing empty field [REQ: a-project-s-files-can-be-listed]
- [x] 1.2 Unit test: a fixture repository holding a file whose name carries non-ASCII bytes lists that name unquoted, and the same string opens it through the content endpoint [REQ: a-project-s-files-can-be-listed]
- [x] 1.3 Prove the test is a test — stash the `-z` change, rerun, and confirm it FAILS (a quoted path assertion that passes either way proves nothing) [REQ: a-project-s-files-can-be-listed]

## 2. The ignored flag

- [x] 2.1 `_git_files(root, include_ignored)` — with the flag, run without `--exclude-standard` and drop any path with a `_SKIP_DIRS` component; record which entries are ignored-only by set-differencing against the unwidened answer [REQ: ignored-files-can-be-listed-on-request]
- [x] 2.2 `list_files(root, ignored: bool = False)` — the flag reaches the endpoint, defaults off, and the answer echoes it; cap and truncation reporting are unchanged [REQ: ignored-files-can-be-listed-on-request]
- [x] 2.3 Unit tests: flag off lists nothing ignored; flag on lists an ignored directory's files and marks them; flag on still excludes a `node_modules` path; the cap still reports truncation with the flag on [REQ: ignored-files-can-be-listed-on-request]

## 3. Version-control status in the listing

- [x] 3.1 `_git_status(root)` — `git status --porcelain -z -uall`, parsing `XY<space><path>\0` and consuming the extra NUL field of a rename/copy entry [REQ: the-listing-carries-each-path-s-version-control-status]
- [x] 3.2 Return `status` as a map of non-clean paths, `None` when there is no repository or the read failed; a failed read logs at WARNING and never fails the listing [REQ: the-listing-carries-each-path-s-version-control-status]
- [x] 3.3 Mark ignored-only entries in the map with git's own `!!` so one map answers both questions [REQ: the-listing-carries-each-path-s-version-control-status]
- [x] 3.4 Unit tests: modified and untracked are marked and a clean file is absent from the map; a non-repository directory answers `status: null` and NOT `{}`; a rename does not shift the following entries' codes [REQ: the-listing-carries-each-path-s-version-control-status]

## 4. The tree carries status (`fleetFiles.ts`)

- [x] 4.1 `buildTree(paths, status?)` attaches each file's code to its node, leaving the existing single-argument call working [REQ: the-structure-marks-what-is-not-committed]
- [x] 4.2 Roll a subtree summary onto every directory in the same pass — *untracked below* and/or *changed below*, never a two-letter code a directory does not have [REQ: the-structure-marks-what-is-not-committed]
- [x] 4.3 `ancestorsOf(path)` — every directory path between the root and a file, for the reveal [REQ: the-structure-follows-the-file-that-is-open]
- [x] 4.4 Unit tests in `web/tests/unit/fleetFiles.test.ts`: roll-up reaches a directory several levels above a modified file; a clean tree rolls up nothing; `buildTree` with no status behaves exactly as before; `ancestorsOf` on a top-level file returns empty, on a deep file returns each level once [REQ: the-structure-marks-what-is-not-committed]

## 5. The panel: marks, and following the open file

- [x] 5.1 Fetch the listing with the `ignored` flag and keep `status` in state; treat a missing map as "no claim" and mark nothing [REQ: the-structure-marks-what-is-not-committed]
- [x] 5.2 `Node` renders a mark for a file's own status and for a directory's roll-up, with untracked visually distinct from changed, and a `title` naming what the mark means [REQ: the-structure-marks-what-is-not-committed]
- [x] 5.3 Ignored entries render subordinate to the rest and carry their own mark [REQ: files-the-project-ignores-can-be-shown-on-request]
- [x] 5.4 On the open path changing, add its ancestors to `expanded` (never removing any) and scroll the active row into view with `block: 'nearest'` [REQ: the-structure-follows-the-file-that-is-open]
- [x] 5.5 The reveal fires for all three routes — a click in the tree, a request from a terminal link, and the remembered file restored on reopen [REQ: the-structure-follows-the-file-that-is-open]

## 6. The panel: two header controls

- [x] 6.1 Word-wrap `IconButton` in the header, `active` when on, driving Monaco's `wordWrap` option; default off [REQ: long-lines-can-be-wrapped-and-the-choice-is-the-reader-s]
- [x] 6.2 Ignored-files `IconButton` beside it, `active` when on, re-fetching the listing on change, its label stating what is being withheld when it is off [REQ: files-the-project-ignores-can-be-shown-on-request]
- [x] 6.3 Both flags read from and written to `localStorage` behind try/catch, so a browser that refuses storage loses the preference and not the panel [REQ: long-lines-can-be-wrapped-and-the-choice-is-the-reader-s]

## 7. Component tests and the visual check

- [x] 7.1 Component tests: wrap toggle flips the editor option and survives a remount; ignored toggle re-requests the listing with the flag; a modified file and its collapsed ancestor both carry a mark; opening a deep file expands its ancestors and leaves unrelated expansions alone [REQ: the-structure-follows-the-file-that-is-open]
- [x] 7.2 `pnpm build` in `web/` and `tsc -b` clean (`tsc --noEmit` alone measures nothing here) [REQ: the-structure-marks-what-is-not-committed]
- [x] 7.3 Python and web unit suites run, compared as a SET DIFF against a baseline actually taken on HEAD — never against a remembered failure count [REQ: the-listing-carries-each-path-s-version-control-status]
- [ ] 7.4 **LOOK AT IT** in the browser against the running dashboard: open the file view on a project with an ignored framework directory, toggle both controls, open a deep file from a terminal link, and confirm the marks, the reveal and the wrap with your eyes. If the browser cannot be reached this task stays OPEN and is said so in the commit [REQ: files-the-project-ignores-can-be-shown-on-request]

## Acceptance Criteria (from spec scenarios)

### A project's files can be listed

- [x] AC-1: WHEN a project's files are listed and the project ignores a directory of build output THEN no file from that directory appears, and an uncommitted working-tree file does [REQ: a-project-s-files-can-be-listed, scenario: the-listing-follows-the-project-s-own-ignore-rules]
- [x] AC-2: WHEN a project holds a file whose name contains bytes outside ASCII THEN the listing carries that name as it is on disk, and the same path sent back opens that file [REQ: a-project-s-files-can-be-listed, scenario: a-path-with-a-non-ascii-name-arrives-intact]
- [x] AC-3: WHEN a project holds more files than the cap THEN the answer carries the entries and the fact that it was cut, with the cap and the true count [REQ: a-project-s-files-can-be-listed, scenario: a-truncated-listing-says-it-is-truncated]
- [x] AC-4: WHEN the listing is asked for a root the screen does not know THEN it refuses and says nothing about what exists on the machine [REQ: a-project-s-files-can-be-listed, scenario: a-root-the-screen-does-not-know-is-refused]

### Ignored files can be listed on request

- [x] AC-5: WHEN the listing is requested without the flag THEN no ignored file appears [REQ: ignored-files-can-be-listed-on-request, scenario: the-flag-is-not-given]
- [x] AC-6: WHEN the listing is requested with the flag THEN the ignored framework directory's files appear marked as ignored, while build-output and dependency directories still do not [REQ: ignored-files-can-be-listed-on-request, scenario: the-flag-is-given]
- [x] AC-7: WHEN the flag is given for a project whose ignored files exceed the cap THEN the answer is still capped and still reports that it was cut [REQ: ignored-files-can-be-listed-on-request, scenario: the-flag-does-not-lift-the-cap]

### The listing carries each path's version-control status

- [x] AC-8: WHEN a project has one edited tracked file and one never-committed file THEN the listing marks the first modified, the second untracked, and marks nothing for unchanged files [REQ: the-listing-carries-each-path-s-version-control-status, scenario: a-modified-and-an-untracked-file-are-both-marked]
- [x] AC-9: WHEN the listing is asked for a directory that is not version-controlled THEN it carries the walked files and NO status map, distinct from a present-but-empty map [REQ: the-listing-carries-each-path-s-version-control-status, scenario: a-project-that-is-not-a-repository-reports-no-status]
- [x] AC-10: WHEN the status of a project cannot be determined THEN the listing still answers with its files and carries no status map [REQ: the-listing-carries-each-path-s-version-control-status, scenario: status-that-cannot-be-read-does-not-lose-the-listing]

### Long lines can be wrapped, and the choice is the reader's

- [x] AC-11: WHEN the reader turns the wrap control on with a too-wide line open THEN that line wraps within the editor's width and needs no horizontal scrolling [REQ: long-lines-can-be-wrapped-and-the-choice-is-the-reader-s, scenario: a-long-line-is-wrapped-on-request]
- [x] AC-12: WHEN a file is opened in a panel whose control was never touched THEN long lines extend beyond the width and the control shows wrapping is off [REQ: long-lines-can-be-wrapped-and-the-choice-is-the-reader-s, scenario: wrapping-is-off-until-it-is-asked-for]
- [x] AC-13: WHEN the reader turns wrapping on and then docks or enlarges the panel THEN wrapping is still on [REQ: long-lines-can-be-wrapped-and-the-choice-is-the-reader-s, scenario: the-choice-survives-the-panel-being-rebuilt]

### Files the project ignores can be shown on request

- [x] AC-14: WHEN the reader turns the ignored-files control on for a project ignoring a framework directory THEN that directory's files appear, marked as ignored, and open like any other [REQ: files-the-project-ignores-can-be-shown-on-request, scenario: an-ignored-directory-appears-when-asked-for]
- [x] AC-15: WHEN the panel is showing only non-ignored files THEN the control shows that ignored files are being withheld [REQ: files-the-project-ignores-can-be-shown-on-request, scenario: the-control-s-state-is-visible]

### The structure marks what is not committed

- [x] AC-16: WHEN the structure holds one file edited since its last commit and one never committed THEN each carries a mark, and the two are distinguishable from each other and from an unchanged file [REQ: the-structure-marks-what-is-not-committed, scenario: a-modified-file-and-an-untracked-file-are-marked-differently]
- [x] AC-17: WHEN a file deep inside a collapsed directory is modified THEN that collapsed directory carries a mark, at every level between it and the file [REQ: the-structure-marks-what-is-not-committed, scenario: a-collapsed-directory-shows-that-something-inside-it-changed]
- [x] AC-18: WHEN the project has no version-control status to report THEN no row is marked clean or changed and the panel makes no statement about what is committed [REQ: the-structure-marks-what-is-not-committed, scenario: no-status-means-no-claim]

### The structure follows the file that is open

- [x] AC-19: WHEN a file several directories deep is opened while only the top level is shown THEN each directory on the path is expanded and its row is scrolled into view, marked open [REQ: the-structure-follows-the-file-that-is-open, scenario: a-file-opened-from-a-terminal-link-is-revealed]
- [x] AC-20: WHEN the reader has expanded unrelated directories and then opens a file elsewhere THEN the unrelated directories are still expanded [REQ: the-structure-follows-the-file-that-is-open, scenario: following-does-not-undo-the-reader-s-own-expansions]
