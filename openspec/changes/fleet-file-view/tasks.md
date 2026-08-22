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

- [x] 6.1 Add `@monaco-editor/react` and `monaco-editor` to `web/package.json` [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]
- [x] 6.2 Configure the loader to use the LOCAL bundle and its workers — no CDN — and assert the built asset carries no external loader URL, because a CDN fallback works on this machine and fails on an offline one [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]
- [x] 6.3 Import Monaco lazily inside the panel's effect, as `FleetTerminal` does with xterm; record the built chunk size in the commit rather than calling it fine [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]

## 7. The panel

- [x] 7.1 `FleetFileView.tsx` — the project's structure on the left, the opened file on the right, and a new panel type registered with the existing dock model [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]
- [x] 7.2 Build the directory tree in the browser from the flat list; mark which file is open [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]
- [x] 7.3 A file type with no highlighting renders as plain text rather than failing to open [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]
- [x] 7.4 Open at a line: scroll it into view and mark it [REQ: the-panel-opens-at-a-named-line-and-marks-it]
- [x] 7.5 A line past the end of the file opens the file at its end and says the line was not there [REQ: the-panel-opens-at-a-named-line-and-marks-it]
- [x] 7.6 Refusals — too large, not text, unreadable — are stated where the content would be, naming the file [REQ: what-cannot-be-shown-is-stated-in-the-panel]
- [x] 7.7 An empty file shows as empty and says so, and is not reported as unreadable [REQ: what-cannot-be-shown-is-stated-in-the-panel]

## 8. Editing and saving

- [x] 8.1 Editing marks the file unsaved and enables the save control [REQ: an-edited-file-is-visibly-unsaved-until-it-is-saved]
- [x] 8.2 Opening another file with unsaved edits asks first [REQ: an-edited-file-is-visibly-unsaved-until-it-is-saved]
- [x] 8.3 An accepted save clears the mark and adopts the returned identity, so the NEXT save is checked against what was actually written [REQ: an-edited-file-is-visibly-unsaved-until-it-is-saved]
- [x] 8.4 A refused save keeps the reader's text, says the file changed, and writes nothing [REQ: a-refused-save-is-reported-never-discarded]
- [x] 8.5 Loading what is on disk after a refusal is an explicit choice that says it replaces the reader's text [REQ: a-refused-save-is-reported-never-discarded]
- [x] 8.6 A test asserts no file content or path reaches browser storage, in the shape `fleetInstructSurface.test.tsx:251` already uses for a declared focus [REQ: nothing-about-a-projects-files-is-kept-in-the-browser]

## 9. The terminal reference

- [x] 9.1 `fileReference(token, projectRoot)` in `web/src/lib/` — a pure function returning the path and optional line, or `null`; unit-tested on the shapes this repo's own tools print [REQ: a-file-reference-in-terminal-output-is-recognised]
- [x] 9.2 Register a link provider on the terminal using it; a path that does not resolve inside the agent's project root stays ordinary text [REQ: a-file-reference-in-terminal-output-is-recognised]
- [x] 9.3 Activation opens the file view at the line; nothing opens without a person's act [REQ: activating-a-reference-opens-it-in-the-file-view]
- [x] 9.4 **MEASURE, on a live agent with `enable-mouse-events` on, whether a click reaches the linkifier at all, and with which modifier.** Write the result — command, what was clicked, what happened — into the change before wiring any control to it [REQ: the-reference-is-reachable-while-the-agent-holds-the-mouse]
- [x] 9.5 Wire the route the measurement supports and state the modifier on screen; if no mouse route reaches the terminal, offer none and say the file list is the way [REQ: the-reference-is-reachable-while-the-agent-holds-the-mouse]
- [x] 9.6 A regression test that the URL path is untouched: an http address still opens in a new tab, a `javascript:` address still opens nowhere [REQ: an-external-url-keeps-its-existing-behaviour]

## 9b. Found by LOOKING, and added to the change rather than absorbed silently

- [x] 9b.1 The listing is fetched once, so a file created while the panel is open never appeared. A refresh control was added — the endpoint runs `git ls-files` on a real tree, so a poll would cost that repeatedly for a reader looking at one file [REQ: a-projects-files-can-be-listed]
- [x] 9b.2 The link provider was registered inside the socket effect, which depends on `label` alone — so it would have been registered once, with an empty file set, and never again: file links would silently never appear. Moved to its own effect over a ref to the emulator, so no re-attach and no replay [REQ: a-file-reference-in-terminal-output-is-recognised]
- [x] 9b.3 Activation requires Ctrl/Cmd. A plain click in a terminal is how a reader focuses it, places a cursor or selects; opening a file on every one would take the screen somewhere nobody asked to go [REQ: activating-a-reference-opens-it-in-the-file-view]

## 9c. Reported by the user after LOOKING at it, 2026-08-22

- [x] 9c.1 *"becsuktam jobbra és nem tudom kinyitni"* — openness and placement were ONE fact, so a band tidied to its strip counted as open and the control did nothing. They are two now: an open set, and the dock map that says where [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]
- [x] 9c.2 *"nincs rajta ugyanolyan layout gombok mint az agenteken"* — the panel carries the same four edge controls, from the SAME list `TileControls` uses, so there is one answer to where a panel may go [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]
- [x] 9c.3 *"nem csak jobb oldalt akarom tartani, hanem ugyanúgy rendezni mint agentek nézetét"* — open and undocked now renders as a TILE in the agent grid, under the same column choice and row height. Measured by clicking: grid → left → grid → top → right [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]
- [x] 9c.4 A stored arrangement brought the panel back docked without anybody opening it, so pressing its edge undocked it into a grid that had no reason to draw it and the panel VANISHED — a control reading "move this" doing "delete this". A dock entry now implies openness [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]
- [x] 9c.5 *"kell a layout határokhoz allitható húzható méret"* — measured: both dividers were ALREADY draggable (`role="separator"`, project list at x=344, the band's inner edge at x=1353). What was missing is the affordance: a 1 px line in the same neutral as the surface behind it. It now carries a grip [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]

- [x] 9c.6 *"files maximize mar van?"* — nem volt; most van. A fájlnézet kitölti a panelt, az agentek a tab-csíkba mennek, és a kettő KIZÁRJA egymást: egy dolog lehet nagy. Mérve: `max=on`, 0 agent-csempe, 10 tab [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]

- [x] 9c.7 **The open risk closed by the USER's own measurement, 2026-08-22:** *"ctrl-click mérés mukodott"*. So a Ctrl+click on a path in a live agent's terminal does reach the emulator and open the file. What is theirs and not mine is stated as theirs: this was measured by the reader on the running screen, not by a check in this repository [REQ: the-reference-is-reachable-while-the-agent-holds-the-mouse]
- [x] 9c.8 *"kellene a file nézet és a file lista közötti savot is tudnk húzogatni"* — the same `FleetSplitter` the project list and the bands use, so there is one answer to what a divider is. Held in the component, because a panel that can sit in the grid or on any of four edges wants a different width in each [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]
- [x] 9c.9 *"a teljes képernyő kell akkor is ha ki van téve 4 iranybol valahova"* — maximising works from a docked band too, and it took THREE measurements to actually work: the write clamped to the drag ceiling (900), then the read clamped it back, and finally `fullBandSize` computed from stale state while subtracting a column that is not inside the shell. Measured after: docked 900 → maximised 1503 → restored 900, in a 1919 px window [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]

- [x] 9c.10 *"hogy tudom csak ugy magatol megnyitni a file bögészót a projektben ha nincs link?"* — there WAS a control: the word `files` in the project title row, between the path and *+ start an agent*, where it read as part of a sentence. Same defect as a divider drawn in the colour behind it: present, and invisible for it. It is now a button in the row that already answers *what is on screen and how*, in the same visual language as the column glyphs, LIT while the panel is open — so it also says whether the files are showing, which the word never did. Rendered outside the `agents.length > 1` guard: a project with one agent has files too [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]

## 10. Looking at it, and closing

- [x] 10.1 LOOK at the panel in the browser on a real project — open a file, jump to a line, edit, save, and force a conflict by changing the file on disk mid-edit. A UI change is not done until somebody looked [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]
- [x] 10.2 Full suites: `pytest tests/unit` set-diffed against a baseline worktree with the import roots asserted, and `pnpm vitest run tests/unit` in `web/` [REQ: the-panel-shows-a-projects-structure-and-one-opened-file]

## 11. Coming back to where the reader was — asked for 2026-08-22

*"files ha bezarom akkor mentse el hol volt hogy ha ujra kinyitom akkor ott legyen"*

- [x] 11.1 `fileToOpen(requested, remembered)` in `fleetFiles.ts` — one line of policy, asymmetric on purpose: an empty path means *just open the panel* and takes the remembered file, a named file always wins so a ctrl-click is never ignored [REQ: closing-the-panel-keeps-where-the-reader-was-for-this-screen-only]
- [x] 11.2 The panel reports the file it opened (`onOpened`), and `Fleet.tsx` holds one remembered file per project root IN MEMORY — never in the stored arrangement, because a path is the consumer's domain [REQ: closing-the-panel-keeps-where-the-reader-was-for-this-screen-only]
- [x] 11.3 `initial` restores it on APPEARING, ref-guarded so it fires once and never over a named request. Found by looking: the panel is torn down for reasons the reader did not ask for — enlarging another panel remounts it — and every one of those read as "the file view forgot" [REQ: closing-the-panel-keeps-where-the-reader-was-for-this-screen-only]
- [x] 11.4 Three tests on the policy, including the refusal (a named file beats the remembered one) [REQ: closing-the-panel-keeps-where-the-reader-was-for-this-screen-only]
- [x] 11.5 LOOKED at it: opened `web/src/lib/fleetFiles.ts:120` from a terminal, closed the panel, opened it from the project header — the same file came back at line 120, marked [REQ: closing-the-panel-keeps-where-the-reader-was-for-this-screen-only]

## 12. What LOOKING found that no test could

- [x] 12.1 **Monaco was measuring itself once.** Without `automaticLayout` the editor kept the size it had at mount, so `revealLineInCenter` centred the target inside a viewport nobody could see: the DOM node was 688 px tall, the mark was IN the DOM, and the line sat at the very top of the visible box — under Monaco's sticky-scroll header. Every panel here is resizable, so a layout measured once is wrong most of the time [REQ: the-panel-opens-at-a-named-line-and-marks-it]
- [x] 12.2 **The line was scrolled to and not MARKED.** Arriving at the right screenful with nothing saying which line was meant is a precise reference delivered imprecisely; there is now a whole-line amber decoration, cleared when a file is opened with no line [REQ: the-panel-opens-at-a-named-line-and-marks-it]
- [x] 12.3 **Ctrl-click could NOT be measured in a terminal whose agent holds the mouse** — `.xterm` carries `enable-mouse-events`, exactly the risk the design names. Shift bypasses the grab (xterm's own force-selection), and shift+ctrl-click opened the file. So the fallback sentence on the panel stays true and stays there [REQ: the-reference-is-reachable-while-the-agent-holds-the-mouse]

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
- [x] AC-15: WHEN the reader picks a file from the structure THEN it appears highlighted and the structure marks it open [REQ: the-panel-shows-a-projects-structure-and-one-opened-file, scenario: a-file-is-opened-from-the-structure]
- [x] AC-16: WHEN the file's type has no highlighting THEN it renders as plain text [REQ: the-panel-shows-a-projects-structure-and-one-opened-file, scenario: a-type-with-no-highlighting-still-renders]
- [x] AC-17: WHEN a file is opened with a line number THEN that line is scrolled into view and marked [REQ: the-panel-opens-at-a-named-line-and-marks-it, scenario: opening-at-a-line-inside-the-file]
- [x] AC-18: WHEN the named line is past the end THEN the file opens at its end and the panel says the line was not there [REQ: the-panel-opens-at-a-named-line-and-marks-it, scenario: a-line-beyond-the-end-of-the-file]
- [x] AC-19: WHEN the endpoint refuses a file THEN the reason stands where the content would be, naming the file [REQ: what-cannot-be-shown-is-stated-in-the-panel, scenario: a-file-the-endpoint-refused]
- [x] AC-20: WHEN an opened file has no content THEN it shows as empty and says so [REQ: what-cannot-be-shown-is-stated-in-the-panel, scenario: an-empty-file-is-not-a-failure]
- [x] AC-21: WHEN the reader changes the content THEN the file is marked unsaved and the save control becomes available [REQ: an-edited-file-is-visibly-unsaved-until-it-is-saved, scenario: editing-marks-the-file-as-unsaved]
- [x] AC-22: WHEN the reader opens another file with unsaved changes THEN the panel asks first [REQ: an-edited-file-is-visibly-unsaved-until-it-is-saved, scenario: leaving-a-file-with-unsaved-edits]
- [x] AC-23: WHEN a save is accepted THEN the unsaved mark clears and the returned identity is adopted [REQ: an-edited-file-is-visibly-unsaved-until-it-is-saved, scenario: a-save-that-succeeded-says-so]
- [x] AC-24: WHEN a save is refused because the file changed THEN the reader's text remains, the panel says so, and nothing was written [REQ: a-refused-save-is-reported-never-discarded, scenario: an-agent-changed-the-file-while-the-reader-was-typing]
- [x] AC-25: WHEN the reader chooses to load what is on disk THEN the panel says it replaces their text and does it only on that choice [REQ: a-refused-save-is-reported-never-discarded, scenario: the-reader-asks-to-see-the-current-file]
- [x] AC-26: WHEN the dashboard is reloaded after a file was opened THEN no content and no path is recovered from storage [REQ: nothing-about-a-projects-files-is-kept-in-the-browser, scenario: a-reload-starts-from-nothing]
- [x] AC-27: WHEN the output contains a project-relative path with a colon and a number THEN it is a reference to that file at that line [REQ: a-file-reference-in-terminal-output-is-recognised, scenario: a-relative-path-with-a-line-number]
- [x] AC-28: WHEN the output contains an absolute path inside the project root THEN it is a reference to that file [REQ: a-file-reference-in-terminal-output-is-recognised, scenario: an-absolute-path-inside-the-project]
- [x] AC-29: WHEN the output contains a path outside the project root THEN it stays ordinary text [REQ: a-file-reference-in-terminal-output-is-recognised, scenario: a-path-outside-the-project-is-not-a-link]
- [x] AC-30: WHEN a person activates a recognised reference THEN the file view opens it at the named line [REQ: activating-a-reference-opens-it-in-the-file-view, scenario: the-reader-activates-a-reference]
- [x] AC-31: WHEN an agent prints a file reference THEN nothing opens until a person acts [REQ: activating-a-reference-opens-it-in-the-file-view, scenario: output-alone-opens-nothing]
- [x] AC-32: WHEN mouse activation reaches the terminal in the running system THEN that route is offered and its modifier is stated on screen [REQ: the-reference-is-reachable-while-the-agent-holds-the-mouse, scenario: mouse-activation-is-available]
- [x] AC-33: WHEN the agent's program consumes the click THEN the file is still reachable without the mouse and the screen states that route [REQ: the-reference-is-reachable-while-the-agent-holds-the-mouse, scenario: mouse-activation-does-not-reach-the-terminal]
- [x] AC-34: WHEN the output contains an http or https address THEN it still opens in a new tab and not in the file view [REQ: an-external-url-keeps-its-existing-behaviour, scenario: a-url-in-the-output]
- [x] AC-35: WHEN the output contains a scheme that could run code THEN it is not opened at all [REQ: an-external-url-keeps-its-existing-behaviour, scenario: a-scheme-that-could-execute-something]
- [x] AC-36: WHEN the reader closes the file view and opens it again from the project header THEN the file they were reading is open again, at the line it was opened at [REQ: closing-the-panel-keeps-where-the-reader-was-for-this-screen-only, scenario: the-panel-is-closed-and-opened-again]
- [x] AC-37: WHEN a reference names a file and another file is remembered THEN the named file opens and the remembered one does not [REQ: closing-the-panel-keeps-where-the-reader-was-for-this-screen-only, scenario: a-file-is-named-while-another-is-remembered]
- [x] AC-38: WHEN the dashboard is reloaded THEN nothing about the previously open file is recovered [REQ: closing-the-panel-keeps-where-the-reader-was-for-this-screen-only, scenario: the-dashboard-is-reloaded]
