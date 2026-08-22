## 1. The server side — listing

- [x] 1.1 New router `lib/set_orch/api/files.py` following the `api/orchestration.py:386` shape (module-level `APIRouter`, `HTTPException` for every refusal), registered in `api/__init__.py` **after** `fleet_router` so `/api/fleet/...` keeps its precedence (CB-16) [REQ: a-projects-files-can-be-listed]
- [x] 1.2 `GET /api/fleet/files?root=` — `git ls-files --cached --others --exclude-standard` in the project root, returning the paths. Root-based and guarded by `_known_roots()`, NOT `_resolve_project()`: measured 2026-08-22, two of the projects on the screen are absent from the registry, so a name lookup would refuse a project the reader is looking at [REQ: a-projects-files-can-be-listed]
- [x] 1.3 The bounded-walk fallback for a project that is not a git repository, and a field in the answer saying WHICH source produced the list [REQ: a-projects-files-can-be-listed]
- [x] 1.4 The cap, and the answer carrying `truncated`, the cap and the true count — never a short list that reads as complete [REQ: a-projects-files-can-be-listed]
- [x] 1.5 A root the screen does not know is refused, and says nothing about what else exists [REQ: a-projects-files-can-be-listed]

## 2. The server side — reading one file

- [x] 2.1 `GET /api/fleet/files/content?root=&path=` returning the text and a sha256 of the exact bytes served [REQ: one-files-content-can-be-read]
- [x] 2.2 The size cap, refusing with the file's size and the cap rather than a truncated prefix [REQ: one-files-content-can-be-read]
- [x] 2.3 Binary refusal — undecodable bytes produce a reason and no partial content [REQ: one-files-content-can-be-read]

## 3. The guard, before anything is read or written

- [x] 3.1 `_confine(project_root, rel_path)` — resolve with symlinks followed, then require `is_relative_to` a registered root, copying the `media.py:238-262` + `fleet.py:667 _known_roots()` shapes [REQ: every-path-is-confined-to-a-known-project-root]
- [x] 3.2 The refusal is byte-identical for a path that exists and one that does not, so the endpoint cannot probe the filesystem [REQ: every-path-is-confined-to-a-known-project-root]
- [x] 3.3 Unit tests against a real temporary tree: `..` traversal, a symlink whose target is outside, a symlinked parent directory, and an absolute path in another project [REQ: every-path-is-confined-to-a-known-project-root]
- [x] 3.4 **Prove the guard is a guard**: mutate `_confine` to check the unresolved path and confirm the symlink test goes red; restore and grep-verify the restore [REQ: every-path-is-confined-to-a-known-project-root]

## 4. The server side — writing

- [x] 4.1 `PUT /api/fleet/files/content` taking the content and the identity the caller last read; write only on a match, and answer with the identity of what was written [REQ: a-file-is-written-back-only-if-it-has-not-changed-underneath]
- [x] 4.2 A mismatched identity is refused with 409, the file untouched, the answer saying the file changed [REQ: a-file-is-written-back-only-if-it-has-not-changed-underneath]
- [x] 4.3 A write to a path that no longer exists is refused rather than re-creating the file [REQ: a-file-is-written-back-only-if-it-has-not-changed-underneath]
- [x] 4.4 Write atomically (temp file in the same directory, then replace) so a failure cannot leave a half-written file [REQ: a-file-is-written-back-only-if-it-has-not-changed-underneath]
- [x] 4.5 An accepted write logs project, path and byte count at INFO — and a test asserts no log record carries file content [REQ: the-framework-persists-nothing-it-read]

## 5. Confidentiality on the server

- [x] 5.1 No caching layer between the endpoint and disk; a test reads the same file twice after changing it and gets the new bytes [REQ: the-framework-persists-nothing-it-read]
- [x] 5.2 Every failure path logs the reason and the path shape only; a test with distinctive content asserts that content appears in no emitted log record [REQ: the-framework-persists-nothing-it-read]

## 6. Monaco enters the dashboard

- [ ] 6.1 Add `@monaco-editor/react` and `monaco-editor` to `web/package.json` [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]
- [ ] 6.2 Configure the loader to use the LOCAL bundle and its workers — no CDN — and assert the built asset carries no external loader URL, because a CDN fallback works on this machine and fails on an offline one [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]
- [ ] 6.3 Import Monaco lazily inside the panel's effect, as `FleetTerminal` does with xterm; record the built chunk size in the commit rather than calling it fine [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]

## 7. The panel

- [ ] 7.1 `FleetFileView.tsx` — the project's structure on the left, the opened file on the right, and a new panel type registered with the existing dock model [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]
- [ ] 7.2 Build the directory tree in the browser from the flat list; mark which file is open [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]
- [ ] 7.3 A file type with no highlighting renders as plain text rather than failing to open [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]
- [ ] 7.4 Open at a line: scroll it into view and mark it [REQ: the-panel-opens-at-a-named-line-and-marks-it]
- [ ] 7.5 A line past the end of the file opens the file at its end and says the line was not there [REQ: the-panel-opens-at-a-named-line-and-marks-it]
- [ ] 7.6 Refusals — too large, not text, unreadable — are stated where the content would be, naming the file [REQ: what-cannot-be-shown-is-stated-in-the-panel]
- [ ] 7.7 An empty file shows as empty and says so, and is not reported as unreadable [REQ: what-cannot-be-shown-is-stated-in-the-panel]

## 8. Editing and saving

- [ ] 8.1 Editing marks the file unsaved and enables the save control [REQ: an-edited-file-is-visibly-unsaved-until-it-is-saved]
- [ ] 8.2 Opening another file with unsaved edits asks first [REQ: an-edited-file-is-visibly-unsaved-until-it-is-saved]
- [ ] 8.3 An accepted save clears the mark and adopts the returned identity, so the NEXT save is checked against what was actually written [REQ: an-edited-file-is-visibly-unsaved-until-it-is-saved]
- [ ] 8.4 A refused save keeps the reader's text, says the file changed, and writes nothing [REQ: a-refused-save-is-reported-never-discarded]
- [ ] 8.5 Loading what is on disk after a refusal is an explicit choice that says it replaces the reader's text [REQ: a-refused-save-is-reported-never-discarded]
- [ ] 8.6 A test asserts no file content or path reaches browser storage, in the shape `fleetInstructSurface.test.tsx:251` already uses for a declared focus [REQ: nothing-about-a-projects-files-is-kept-in-the-browser]

## 9. The terminal reference

- [ ] 9.1 `fileReference(token, projectRoot)` in `web/src/lib/` — a pure function returning the path and optional line, or `null`; unit-tested on the shapes this repo's own tools print [REQ: a-file-reference-in-terminal-output-is-recognised]
- [ ] 9.2 Register a link provider on the terminal using it; a path that does not resolve inside the agent's project root stays ordinary text [REQ: a-file-reference-in-terminal-output-is-recognised]
- [ ] 9.3 Activation opens the file view at the line; nothing opens without a person's act [REQ: activating-a-reference-opens-it-in-the-file-view]
- [ ] 9.4 **MEASURE, on a live agent with `enable-mouse-events` on, whether a click reaches the linkifier at all, and with which modifier.** Write the result — command, what was clicked, what happened — into the change before wiring any control to it [REQ: the-reference-is-reachable-while-the-agent-holds-the-mouse]
- [ ] 9.5 Wire the route the measurement supports and state the modifier on screen; if no mouse route reaches the terminal, offer none and say the file list is the way [REQ: the-reference-is-reachable-while-the-agent-holds-the-mouse]
- [ ] 9.6 A regression test that the URL path is untouched: an http address still opens in a new tab, a `javascript:` address still opens nowhere [REQ: an-external-url-keeps-its-existing-behaviour]

## 10. Looking at it, and closing

- [ ] 10.1 LOOK at the panel in the browser on a real project — open a file, jump to a line, edit, save, and force a conflict by changing the file on disk mid-edit. A UI change is not done until somebody looked [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]
- [ ] 10.2 Full suites: `pytest tests/unit` set-diffed against a baseline worktree with the import roots asserted, and `pnpm vitest run tests/unit` in `web/` [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a project's files are listed and the project ignores a directory of build output THEN no file from it appears and an uncommitted file does [REQ: a-projects-files-can-be-listed, scenario: the-listing-follows-the-projects-own-ignore-rules]
- [x] AC-2: WHEN a project holds more files than the cap THEN the answer carries the entries, the cap and the true count [REQ: a-projects-files-can-be-listed, scenario: a-truncated-listing-says-it-is-truncated]
- [x] AC-3: WHEN the listing is asked for a root the screen does not know THEN it refuses and says nothing about what exists [REQ: a-projects-files-can-be-listed, scenario: a-root-the-screen-does-not-know-is-refused]
- [x] AC-4: WHEN a readable text file is requested THEN its content and a content identity are returned [REQ: one-files-content-can-be-read, scenario: a-text-file-is-returned-with-its-identity]
- [x] AC-5: WHEN the file is larger than the cap THEN the refusal states the size and the cap [REQ: one-files-content-can-be-read, scenario: a-file-too-large-to-serve-is-refused-with-its-size]
- [x] AC-6: WHEN the file is not decodable text THEN it is refused with a reason and no partial content [REQ: one-files-content-can-be-read, scenario: a-binary-file-is-refused-rather-than-mangled]
- [x] AC-7: WHEN a write carries the identity that still matches disk THEN it is written and the new identity returned [REQ: a-file-is-written-back-only-if-it-has-not-changed-underneath, scenario: the-file-is-unchanged-since-it-was-read]
- [x] AC-8: WHEN a write carries a stale identity THEN it is refused, the file keeps the other writer's content, and the answer says it changed [REQ: a-file-is-written-back-only-if-it-has-not-changed-underneath, scenario: an-agent-changed-the-file-while-it-was-open]
- [x] AC-9: WHEN a write names a path that no longer exists THEN it is refused rather than re-creating it [REQ: a-file-is-written-back-only-if-it-has-not-changed-underneath, scenario: a-write-to-a-file-that-has-since-been-deleted]
- [x] AC-10: WHEN a request climbs out of the project root THEN it is refused and nothing is read or written [REQ: every-path-is-confined-to-a-known-project-root, scenario: a-traversal-out-of-the-project-is-refused]
- [x] AC-11: WHEN the path is or lies under a link resolving outside every known root THEN it is refused on the RESOLVED path [REQ: every-path-is-confined-to-a-known-project-root, scenario: a-symbolic-link-pointing-outside-the-project-is-refused]
- [x] AC-12: WHEN a path outside every known root is requested THEN the answer is the same whether or not it exists [REQ: every-path-is-confined-to-a-known-project-root, scenario: the-refusal-does-not-answer-whether-the-file-exists]
- [x] AC-13: WHEN a read or write fails and is logged THEN the record carries project and reason and no line of the file [REQ: the-framework-persists-nothing-it-read, scenario: a-failure-is-logged-without-the-content]
- [x] AC-14: WHEN the same file is read twice THEN the second answer comes from disk and no copy is held [REQ: the-framework-persists-nothing-it-read, scenario: nothing-is-cached-between-requests]
- [ ] AC-15: WHEN the reader picks a file from the structure THEN it appears highlighted and the structure marks it open [REQ: the-panel-shows-a-projects-structure-and-one-opened-file, scenario: a-file-is-opened-from-the-structure]
- [ ] AC-16: WHEN the file's type has no highlighting THEN it renders as plain text [REQ: the-panel-shows-a-projects-structure-and-one-opened-file, scenario: a-type-with-no-highlighting-still-renders]
- [ ] AC-17: WHEN a file is opened with a line number THEN that line is scrolled into view and marked [REQ: the-panel-opens-at-a-named-line-and-marks-it, scenario: opening-at-a-line-inside-the-file]
- [ ] AC-18: WHEN the named line is past the end THEN the file opens at its end and the panel says the line was not there [REQ: the-panel-opens-at-a-named-line-and-marks-it, scenario: a-line-beyond-the-end-of-the-file]
- [ ] AC-19: WHEN the endpoint refuses a file THEN the reason stands where the content would be, naming the file [REQ: what-cannot-be-shown-is-stated-in-the-panel, scenario: a-file-the-endpoint-refused]
- [ ] AC-20: WHEN an opened file has no content THEN it shows as empty and says so [REQ: what-cannot-be-shown-is-stated-in-the-panel, scenario: an-empty-file-is-not-a-failure]
- [ ] AC-21: WHEN the reader changes the content THEN the file is marked unsaved and the save control becomes available [REQ: an-edited-file-is-visibly-unsaved-until-it-is-saved, scenario: editing-marks-the-file-as-unsaved]
- [ ] AC-22: WHEN the reader opens another file with unsaved changes THEN the panel asks first [REQ: an-edited-file-is-visibly-unsaved-until-it-is-saved, scenario: leaving-a-file-with-unsaved-edits]
- [ ] AC-23: WHEN a save is accepted THEN the unsaved mark clears and the returned identity is adopted [REQ: an-edited-file-is-visibly-unsaved-until-it-is-saved, scenario: a-save-that-succeeded-says-so]
- [ ] AC-24: WHEN a save is refused because the file changed THEN the reader's text remains, the panel says so, and nothing was written [REQ: a-refused-save-is-reported-never-discarded, scenario: an-agent-changed-the-file-while-the-reader-was-typing]
- [ ] AC-25: WHEN the reader chooses to load what is on disk THEN the panel says it replaces their text and does it only on that choice [REQ: a-refused-save-is-reported-never-discarded, scenario: the-reader-asks-to-see-the-current-file]
- [ ] AC-26: WHEN the dashboard is reloaded after a file was opened THEN no content and no path is recovered from storage [REQ: nothing-about-a-projects-files-is-kept-in-the-browser, scenario: a-reload-starts-from-nothing]
- [ ] AC-27: WHEN the output contains a project-relative path with a colon and a number THEN it is a reference to that file at that line [REQ: a-file-reference-in-terminal-output-is-recognised, scenario: a-relative-path-with-a-line-number]
- [ ] AC-28: WHEN the output contains an absolute path inside the project root THEN it is a reference to that file [REQ: a-file-reference-in-terminal-output-is-recognised, scenario: an-absolute-path-inside-the-project]
- [ ] AC-29: WHEN the output contains a path outside the project root THEN it stays ordinary text [REQ: a-file-reference-in-terminal-output-is-recognised, scenario: a-path-outside-the-project-is-not-a-link]
- [ ] AC-30: WHEN a person activates a recognised reference THEN the file view opens it at the named line [REQ: activating-a-reference-opens-it-in-the-file-view, scenario: the-reader-activates-a-reference]
- [ ] AC-31: WHEN an agent prints a file reference THEN nothing opens until a person acts [REQ: activating-a-reference-opens-it-in-the-file-view, scenario: output-alone-opens-nothing]
- [ ] AC-32: WHEN mouse activation reaches the terminal in the running system THEN that route is offered and its modifier is stated on screen [REQ: the-reference-is-reachable-while-the-agent-holds-the-mouse, scenario: mouse-activation-is-available]
- [ ] AC-33: WHEN the agent's program consumes the click THEN the file is still reachable without the mouse and the screen states that route [REQ: the-reference-is-reachable-while-the-agent-holds-the-mouse, scenario: mouse-activation-does-not-reach-the-terminal]
- [ ] AC-34: WHEN the output contains an http or https address THEN it still opens in a new tab and not in the file view [REQ: an-external-url-keeps-its-existing-behaviour, scenario: a-url-in-the-output]
- [ ] AC-35: WHEN the output contains a scheme that could run code THEN it is not opened at all [REQ: an-external-url-keeps-its-existing-behaviour, scenario: a-scheme-that-could-execute-something]
