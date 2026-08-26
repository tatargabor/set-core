## 1. The endpoint (core, `lib/set_orch/api/`)

- [x] 1.1 Create `lib/set_orch/api/desktop.py` with `POST /api/desktop/open` taking one absolute path and answering `{opened, path}` or an HTTP refusal carrying the reason [REQ: one-path-can-be-handed-to-the-desktop]
- [x] 1.2 Implement the guard in the order design D2 fixes — absolute → realpath → exists → regular file or directory → `.desktop` → executable bit on REGULAR FILES ONLY — with each refusal naming which rule it hit [REQ: what-must-never-be-handed-over]
- [x] 1.3 Hand over with `subprocess.Popen(["xdg-open", path], start_new_session=True)` and all three streams at `DEVNULL`; never read the file, never copy it, log the path and the outcome only [REQ: the-endpoint-reads-nothing-and-persists-nothing]
- [x] 1.4 Refuse with "no desktop handler available" when `shutil.which("xdg-open")` is empty, and word the success answer as *the desktop was asked*, not *a window opened* [REQ: a-refusal-is-an-answer-not-a-silence]
- [x] 1.5 Register the router in `lib/set_orch/api/__init__.py` immediately after `files_router`, before every `/api/{project}/…` family (CB-16 ordering), with the reason stated in a comment [REQ: one-path-can-be-handed-to-the-desktop]

## 2. What counts as an external reference (web lib)

- [x] 2.1 Add `externalReference(token, root?)` to `web/src/lib/fleetFiles.ts`: shared punctuation stripping, leading `/` required, `://` refused, trailing `:<line>` stripped, and `null` when the path lies inside the known project root [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 2.2 Document in the function itself that the in-project route wins, so precedence is decided in one place rather than by link-provider registration order [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]

## 3. The terminal (web component)

- [x] 3.1 Extend `FleetTerminal`'s link provider so it also runs when no project context is present, offering external links there, and keeps `fileReference` first when it is [REQ: activating-a-desktop-reference-hands-it-to-the-desktop]
- [x] 3.2 Activate an external link on ctrl/cmd-click only — a plain click stays the terminal's — and POST the path to `/api/desktop/open` from the component itself [REQ: activating-a-desktop-reference-hands-it-to-the-desktop]
- [x] 3.3 Render both outcomes on the existing status row: a refusal that stays until the next activation, and a success line that auto-clears [REQ: an-activation-that-cannot-be-honoured-says-why]
- [x] 3.4 Verify no code path asks the server whether a path exists before rendering a link [REQ: an-activation-that-cannot-be-honoured-says-why]

## 4. Tests

- [x] 4.1 Python unit tests for the guard: an existing file opens, a directory opens, a missing path, a relative path, a `.desktop` file, an executable file, a symlink whose TARGET is executable, and a directory (whose x bits must not be read as executable) [REQ: what-must-never-be-handed-over]
- [x] 4.2 Python test that the hand-over is detached and that nothing reads file content — assert on the spawned argv, with `subprocess.Popen` patched [REQ: the-endpoint-reads-nothing-and-persists-nothing]
- [x] 4.3 Python test for the missing-handler refusal [REQ: a-refusal-is-an-answer-not-a-silence]
- [x] 4.4 Vitest for `externalReference`: parenthesised path, `path:line`, a URL, a relative token, an in-project absolute path (→ `null`), and a path outside the root [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 4.5 Vitest for the terminal: ctrl-click posts, plain click does not, a refusal is rendered [REQ: an-activation-that-cannot-be-honoured-says-why]
- [x] 4.6 Prove each new test fails without its fix — stash the implementation and rerun (`evidence-discipline`), and record which ones passed either way [REQ: what-must-never-be-handed-over]

## 5. Deploy and look at it

- [x] 5.1 `pnpm build` in `web/` and restart `set-web` so the running service serves the change [REQ: activating-a-desktop-reference-hands-it-to-the-desktop]
- [x] 5.2 Open the fleet screen in the browser, find an absolute out-of-project path in a live terminal, ctrl-click it, and report what actually happened — the application that opened, or the refusal text on the status row. If the browser cannot be reached, this task stays OPEN and says so [REQ: activating-a-desktop-reference-hands-it-to-the-desktop]
  - **DONE, and here is exactly what was seen** (2026-08-26, Chrome on the running dashboard): hovering `/tmp/desktop-open-probe.txt` in a live agent terminal underlined it — measured while the emulator carried `enable-mouse-events`, i.e. with the agent holding the mouse — and a ctrl-click put `handed to the desktop: /tmp/desktop-open-probe.txt` in emerald on the row under the terminal's header.
  - **NOT seen on the live screen: the refusal row.** The terminal used for the check is a live session whose own output moves under the cursor between one tool call and the next, so a click aimed at a bogus path could not be landed twice in a row. The red row is covered by three unit tests and by the endpoint answering `400 no such file or directory` / `400 executable files are not opened` to a live `curl`. Stated rather than implied: nobody has looked at the failure colour on the running screen.
  - **One defect found by looking, and fixed:** the outcome row first carried `data-fleet-terminal-open`, a name the tile's *open a terminal* control already uses (`TileControls.tsx`). It is now `data-fleet-terminal-open-outcome`.

## 6. Relative paths and directories — the second report, same day

- [x] 6.1 Rename `externalReference` to `desktopReference` and extend it: a relative token is resolved against the project root when `fileReference` refused it [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 6.2 Add the shape test (`looksLikePath`): ASCII path characters, at least one slash, and one of a second slash / a trailing slash / a dot-extension — the filter that replaces the known-file set on this route [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 6.3 Strip a trailing slash from the ANSWER but not from the shape test, so `docs/` is recognised and the message names `docs` [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 6.4 Refuse a relative token when no project root is known [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 6.5 Vitest for all of it — the reported directory, `docs/`, an unlisted file, `path:line`, no-root, and four prose tokens (`és/vagy`, `and/or`, `24/7`, `TCP/IP`) [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 6.6 Terminal test: the reported line hands over `<root>/openspec/changes/<name>`, and a line mixing a path with prose underlines only the paths [REQ: activating-a-desktop-reference-hands-it-to-the-desktop]
- [x] 6.7 Mutation-prove each new rule (no-relative, no-shape-filter, no-trailing-slash-signal, root-not-required) — all four killed 2026-08-26 [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 6.8 Rebuild the dashboard so the running service serves the change [REQ: activating-a-desktop-reference-hands-it-to-the-desktop]
- [x] 6.9 Look at a relative directory link in the browser [REQ: activating-a-desktop-reference-hands-it-to-the-desktop]
  - **DONE, and here is exactly what was seen** (2026-08-26, Chrome on the running dashboard): `openspec/changes/fleet-open-external-path/` in a live agent terminal underlined on hover, and a ctrl-click put `handed to the desktop: <repo-root>/openspec/changes/fleet-open-external-path` in emerald on the row under the terminal's header — the trailing slash dropped from the message, the root prepended.
  - **Why it was briefly recorded as blocked:** the first attempt met `Can't interact with browser-internal or unparseable URLs` on every interaction. The cause was not the extension: `set-web` was in `deactivating` at that moment (restarted from another session), so the tab never left `chrome://newtab`, and the extension's refusal named the tab rather than the reason. Kept here because the message points at the wrong thing, and the next reader will meet it again.

## 7. The worktree — the third report, same day

- [x] 7.1 Add `terminalTarget(token, {root, cwd, known})` to `web/src/lib/fleetFiles.ts` as the ONE place that decides a token's destination, and strip the precedence branch out of `desktopReference` [REQ: a-relative-reference-belongs-to-the-agents-own-working-directory]
- [x] 7.2 Resolve a relative token against the agent's `cwd`, falling back to the project root only when no cwd was reported [REQ: a-relative-reference-belongs-to-the-agents-own-working-directory]
- [x] 7.3 SUPERSEDED the same day by 7.9–7.15: the first cut sent every worktree relative token to the desktop, because the file view could not read a worktree. The reader's answer was *what is inside the project and the editor can open, opens in the editor*, so the endpoints were widened instead and the file view now reads the worktree [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor]
- [x] 7.4 An absolute path of ANOTHER checkout goes to the desktop — the file view reads one checkout at a time, and the desktop opens the right content [REQ: a-relative-reference-belongs-to-the-agents-own-working-directory]
- [x] 7.5 Declare `cwd` on `FleetAgent` and pass `agentCwd` from `Fleet.tsx` into the terminal — the payload already carries it, measured on a live agent (`project_root: <p>`, `cwd: <p>-wt-<name>`, `branch: change/<name>`) [REQ: a-relative-reference-belongs-to-the-agents-own-working-directory]
- [x] 7.6 Vitest for `terminalTarget`: the worktree case, the same-path-in-both case, the project-root case, the absolute case, the no-cwd fallback, the docked panel, and prose [REQ: a-relative-reference-belongs-to-the-agents-own-working-directory]
- [x] 7.7 Terminal tests: a worktree agent's relative directory posts the worktree path, and a worktree agent's LISTED file does not reach the file view [REQ: a-relative-reference-belongs-to-the-agents-own-working-directory]
- [x] 7.8 Mutation-prove the rule (worktree rule removed, base swapped to the root, absolute swept into the rule) — all three killed 2026-08-26 [REQ: a-relative-reference-belongs-to-the-agents-own-working-directory]
- [x] 7.9 Reuse `_start_location_verdict` in `lib/set_orch/api/files.py` so the file endpoints serve a worktree of a known project — the two guards had drifted, and the docstring claimed they had not [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor]
- [x] 7.10 Fetch the file listing of every open terminal's agent cwd, not only of the project root [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor]
- [x] 7.11 `terminalTarget` takes the BASE's listing and returns the checkout with a file target; the terminal hands that root to `onOpenFile` [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor]
- [x] 7.12 `FileRequest.from` carries the checkout; `FleetFileView` reads, writes and lists from it, and NAMES it in the header when it is not the project root [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor]
- [x] 7.13 Python tests against a REAL git worktree: it can be listed, its file is read from it and not from main, an unrelated directory and a subdirectory are still refused [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor]
- [x] 7.14 Vitest: the panel reads the worktree, says which checkout, says nothing for the project's own, and writes back to the checkout it read from [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor]
- [x] 7.15 Mutation-prove it — guard back to `_known_roots` (2 killed), base swapped to root, file target's root swapped to root, request checkout ignored (3 killed), save root swapped, header marker removed [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor]
- [ ] 7.16 **OPEN — look at a worktree agent's link in the browser.** Attempted 2026-08-26 and NOT completed, for a reason worth writing down rather than retrying blindly: the only worktree agent on the screen belongs to a live session whose output moves under the cursor between one tool call and the next, so a click aimed at a path lands a few lines off; and clicking around in somebody else's running terminal is itself a side effect. What IS measured: the endpoint serves the real worktree live (`GET /api/fleet/files?root=<project>-wt-<name>` → 30 121 files, `source: git`), the panel's read/write/marker behaviour is held by four unit tests, and the desktop half of the same route was seen working on the live screen earlier today. Nobody has yet SEEN a worktree file open in the internal editor [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor]

## Acceptance Criteria (from spec scenarios)

### desktop-open

- [x] AC-1: WHEN a person activates an absolute path naming an existing regular file THEN the framework asks the desktop to open it and answers that it was handed over [REQ: one-path-can-be-handed-to-the-desktop, scenario: an-existing-file-is-handed-over]
- [x] AC-2: WHEN the activated path names an existing directory THEN it is handed over the same way [REQ: one-path-can-be-handed-to-the-desktop, scenario: an-existing-directory-is-handed-over]
- [x] AC-3: WHEN a path appears in terminal output, a log or a file THEN nothing is opened until a person activates it [REQ: one-path-can-be-handed-to-the-desktop, scenario: nothing-opens-without-an-activation]
- [x] AC-4: WHEN the activated path names a file with an executable bit set THEN it is refused, nothing is started, and the answer names the reason [REQ: what-must-never-be-handed-over, scenario: an-executable-file]
- [x] AC-5: WHEN the activated path names a `.desktop` file THEN it is refused whatever its permissions are [REQ: what-must-never-be-handed-over, scenario: a-desktop-entry]
- [x] AC-6: WHEN the activated path does not exist THEN it is refused with a reason naming that, and no handler is started [REQ: what-must-never-be-handed-over, scenario: a-path-that-is-not-there]
- [x] AC-7: WHEN the request carries a path that is not absolute THEN it is refused [REQ: what-must-never-be-handed-over, scenario: a-relative-path]
- [x] AC-8: WHEN a path is handed to the desktop THEN no content of that file is read and none is stored [REQ: the-endpoint-reads-nothing-and-persists-nothing, scenario: a-file-is-opened]
- [x] AC-9: WHEN the machine has no desktop-open program available THEN the answer is a refusal naming that, not a success [REQ: a-refusal-is-an-answer-not-a-silence, scenario: no-handler-on-this-platform]
- [x] AC-10: WHEN the path is handed over successfully THEN the answer states the desktop was asked, and does not assert that a window opened [REQ: a-refusal-is-an-answer-not-a-silence, scenario: the-answer-is-about-hand-over]

### terminal-file-links

- [x] AC-22: WHEN an agent whose working directory is a worktree prints a relative path THEN it is resolved against that worktree [REQ: a-relative-reference-belongs-to-the-agents-own-working-directory, scenario: an-agent-working-in-a-worktree]
- [x] AC-23: WHEN the relative path is also a file of the project root's listing THEN the worktree's copy is still what is opened [REQ: a-relative-reference-belongs-to-the-agents-own-working-directory, scenario: the-same-relative-path-exists-in-both-checkouts]
- [x] AC-24: WHEN the agent's working directory is the project root THEN a relative path behaves exactly as before [REQ: a-relative-reference-belongs-to-the-agents-own-working-directory, scenario: an-agent-standing-in-the-project-itself]
- [x] AC-26: WHEN the payload carries no working directory THEN the project root is used and the reference is still offered [REQ: a-relative-reference-belongs-to-the-agents-own-working-directory, scenario: no-working-directory-reported]
- [x] AC-27: WHEN a person activates a relative path that is a file of the agent's worktree THEN the file view opens it, reading that worktree [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor, scenario: a-file-of-the-agents-worktree]
- [x] AC-28: WHEN the file view is reading a checkout other than the project root THEN the panel names that checkout [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor, scenario: the-panel-names-the-checkout-it-is-reading]
- [x] AC-29: WHEN a file read from a worktree is edited and saved THEN it is written back to that worktree [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor, scenario: a-save-goes-back-where-the-file-came-from]
- [x] AC-30: WHEN the activated reference names a directory THEN it is handed to the desktop [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor, scenario: a-directory-still-goes-to-the-desktop]
- [x] AC-31: WHEN the file endpoints are asked for a non-prunable worktree of a known project THEN they serve it with the same confinement and limits [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor, scenario: a-worktree-of-a-known-project-may-be-read]
- [x] AC-32: WHEN they are asked for a directory that is neither a known root nor a worktree of one THEN they refuse it [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor, scenario: an-unrelated-directory-is-still-refused]

- [x] AC-11: WHEN the output contains a project-relative path followed by a colon and a number THEN the terminal treats it as a reference to that file at that line [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: a-relative-path-with-a-line-number]
- [x] AC-12: WHEN the output contains an absolute path inside the project root THEN it is treated as a reference to that file [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: an-absolute-path-inside-the-project]
- [x] AC-13: WHEN the output contains an absolute path outside the project root THEN it is recognised as an external reference [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: an-absolute-path-outside-the-project]
- [x] AC-14: WHEN the output contains a relative path that names a directory of the project THEN it is a desktop reference resolved against the root [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: a-relative-directory]
- [x] AC-14b: WHEN the output contains a path-shaped relative token the listing does not have THEN it is a desktop reference rather than text [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: a-relative-path-the-projects-listing-does-not-have]
- [x] AC-14c: WHEN the output contains a word such as `and/or` or `24/7` THEN it is left as ordinary text [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: prose-that-merely-contains-a-slash]
- [x] AC-14d: WHEN a relative token appears in a terminal whose project root is not known THEN it is left as ordinary text [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: a-relative-token-with-no-project-context]
- [x] AC-15: WHEN a person activates a recognised file reference in the terminal THEN the file view opens that file and lands on the named line [REQ: activating-a-reference-opens-it-in-the-file-view, scenario: the-reader-activates-a-reference]
- [x] AC-16: WHEN an agent prints a file reference THEN nothing opens until a person acts on it [REQ: activating-a-reference-opens-it-in-the-file-view, scenario: output-alone-opens-nothing]
- [x] AC-17: WHEN a person activates an absolute path outside the project root THEN the path is handed to the desktop and nothing opens inside the dashboard [REQ: activating-a-desktop-reference-hands-it-to-the-desktop, scenario: the-reader-activates-an-external-path]
- [x] AC-17b: WHEN a person activates a relative directory of the project THEN the resolved absolute path is handed to the desktop and the file manager opens [REQ: activating-a-desktop-reference-hands-it-to-the-desktop, scenario: the-reader-activates-a-directory]
- [x] AC-18: WHEN a person clicks a recognised desktop reference without the activation modifier THEN the click is the terminal's and nothing opens [REQ: activating-a-desktop-reference-hands-it-to-the-desktop, scenario: a-plain-click-still-belongs-to-the-terminal]
- [x] AC-19: WHEN a person activates an external reference whose file does not exist THEN the terminal reports the refusal and its reason [REQ: an-activation-that-cannot-be-honoured-says-why, scenario: the-path-names-nothing]
- [x] AC-20: WHEN the activated external reference names an executable or a desktop entry THEN the terminal reports that it was refused and nothing is started [REQ: an-activation-that-cannot-be-honoured-says-why, scenario: the-path-is-something-that-would-be-run]
- [x] AC-21: WHEN terminal output is rendered THEN the framework does not ask the server whether the paths in it exist [REQ: an-activation-that-cannot-be-honoured-says-why, scenario: no-advance-probing]
