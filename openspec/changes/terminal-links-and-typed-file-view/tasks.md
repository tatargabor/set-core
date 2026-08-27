## 0. Base the change on the spec it modifies

- [ ] 0.1 Archive `fleet-open-external-path` first — this change's MODIFIED requirements are
  the ones that change introduced, so archiving in the other order makes both deltas disagree
  about what the base said. Its single open task (7.16, a browser check on a worktree link) is
  the same look this change performs in §7; do that look, close it, then archive
  [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor]
- [x] 0.2 Record the measurement baseline before touching anything: rerun the corpus harness
  (30 transcripts) against `HEAD` and keep the four counts — desktop-with-existing-path,
  false links, missed links, single-segment absolutes. Every later claim of improvement is a
  set diff against THIS run, not against a remembered number
  [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]

  — **MEASURED at `9437605d`** over the same 30 transcripts (11 596 distinct tokens):
  desktop-with-existing-path **823**, false links (underlined, path absent) **1 746**,
  missed links (names a file that exists, left as text) **252**, single-segment absolute
  tokens **465** of which **425** were false links. Harness and per-token verdict sets kept
  beside the run; every later claim is a set diff against THIS run.

## 1. The recogniser — lib only, measurable without a browser

- [x] 1.1 Replace `unwrap`'s single strip with a CANDIDATE LIST — the token as written, plus
  each progressively unwrapped variant (markdown emphasis `*`, code fences, brackets, quotes,
  a trailing table-cell `|`), each still keeping a trailing `:<digits>` as the line number.
  Resolve candidates in order and take the first that places; VS Code's detector works this
  way because one destructive strip can delete the variant that would have matched
  [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 1.2 Add `~/` expansion against a supplied home directory; a token starting with `~/`
  with no home supplied stays text. The browser never guesses the home
  [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 1.3 Apply the ASCII path-character class to the ABSOLUTE branch too, so route tokens
  carrying `[`, `<` or other non-path characters are text
  [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 1.4 Implement D3's three-tier rule: inside a known checkout → internal; ≥2 segments AND
  an extension → desktop; otherwise path-shaped but unplaceable → LOW CONFIDENCE; neither →
  text [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 1.4b Carry the tier out to the link decoration: a low-confidence link sets
  `ILink.decorations` so it draws no underline and no tooltip, and stays activatable only
  while the modifier is held
  [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 1.5 Implement path-boundary, longest-match checkout resolution (D2), with a test that a
  `<project>-wt-<name>` worktree is not matched by `<project>` and vice versa
  [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor]
- [x] 1.6 Implement suffix resolution (D4): one boundary match resolves; SEVERAL are returned
  as a choice for the reader rather than discarded; none is text. Build the suffix index once
  per listing rather than per token
  [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 1.6b Add the recogniser's limits (D9) — max row length, max references per row, max
  token length — and a test that a row beyond them stops recognition instead of scanning
  [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 1.7 Widen `terminalTarget` to take the known checkouts and the home, and return an
  `internal` target carrying WHICH checkout it resolved to — replacing the single-base
  decision [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor]
- [x] 1.8 Add a `directory` kind to the target union, returned for a token that names a
  directory of a known checkout [REQ: activating-a-directory-reveals-it-in-the-structure-pane]
- [x] 1.9 Unit-test every scenario of the recogniser requirements, including the negative ones
  (`/opsx:ff`, `/api/v1/items`, `and/or`, `24/7`, an ambiguous suffix)
  [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 1.10 **Prove each new test fails without its fix**: `git stash && npx vitest run <file>;
  git stash pop`, asserting BOTH the mutation and the restore. A test that passes either way
  proves nothing and looks like proof forever
  [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 1.11 Rerun the corpus harness against the new lib and diff against 0.2: the
  single-segment false links must be gone, and no previously-correct link may be lost
  [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]

  — **MEASURED, set diff against 0.2:** the 425 single-segment absolute false links are
  **0** — not one is still drawn as a link. Of the **3 339** links that WORKED before,
  **1** is lost (a maildir filename carrying `=`, `,` and `:`). **192** previously
  underlined links are now low confidence — recognised, drawing nothing, reachable on
  modifier-hold. New totals: false desktop links **1 746 → 158**, missed links
  **252 → 72**, panel targets **2 516 → 4 686** (4 080 file, 457 directory, 149 choice).
  **673** references now open the panel on a file that is not there; **656 of them were
  already false links before**, so the reader gets a refusal in the panel instead of a
  desktop error, and 17 are new.

## 2. What the screen knows — the payload fields

- [x] 2.1 Add `home` to the fleet payload, from the framework account, with the type in
  `fleetTypes.ts` [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 2.2 Add `FleetProject.checkouts` — the project root plus its non-prunable worktrees —
  DERIVED from `_start_location_verdict`, not enumerated beside it
  [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor]
- [x] 2.3 Test that `checkouts` and the file endpoints agree for a worktree: what the payload
  lists, `_known_root` accepts; what it omits, it refuses. Two enumerations of "what this
  screen knows" have already drifted here once
  [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor]

## 3. The terminal — routing the activation

- [x] 3.1 Pass the known checkouts and the home into the link provider in `FleetTerminal.tsx`,
  keeping the existing re-registration behaviour when a listing arrives
  [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor]
- [x] 3.2 Route an `internal` target to the file view with the checkout it resolved to; route
  a `directory` target to the panel's reveal; leave `desktop` unchanged
  [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor]
- [x] 3.3 Confirm a path under no registered checkout still reaches the desktop route, and
  that this change relaxes none of its refusals
  [REQ: activating-a-desktop-reference-hands-it-to-the-desktop]
- [x] 3.4 Test that a plain click (no modifier) still belongs to the terminal for every target
  kind, including low-confidence [REQ: activating-a-desktop-reference-hands-it-to-the-desktop]
- [x] 3.5 Present the ambiguous-suffix matches for the reader to choose from, opening nothing
  until they do [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]

## 4. The endpoint — a typed answer

- [ ] 4.1 Rework `read_file` in `lib/set_orch/api/files.py` to decide by decode attempt, with
  a null-byte check, and never by extension or permission bits (D6)
  [REQ: file-content-is-served-typed-by-its-bytes]
- [ ] 4.2 Return a media type and size on the non-text refusal, keeping the size refusal
  distinguishable from the type refusal
  [REQ: file-content-is-served-typed-by-its-bytes]
- [ ] 4.3 Add the raw byte route behind the SAME `_known_root` and `_confine` calls, serving
  only allow-listed non-executing media types, with `nosniff` and an ATTACHMENT
  `Content-Disposition` — the browser must never be asked to interpret the body (D5)
  [REQ: file-content-is-served-typed-by-its-bytes]
- [ ] 4.4 Give the raw route its own higher size cap, and make each refusal name which cap
  fired (D7) [REQ: file-content-is-served-typed-by-its-bytes]
- [ ] 4.5 Test the hostile cases: a path escaping the root, a symlink to outside, a root that
  is not registered, a media type off the allow-list, and an SVG (which must take the TEXT
  route, not the image route) [REQ: file-content-is-served-typed-by-its-bytes]
- [ ] 4.6 Test that a shell script with `+x` is returned as text, and that `Makefile`, `.env`
  and a shebang file with no suffix are too
  [REQ: file-content-is-served-typed-by-its-bytes]

## 4b. The desktop guard — refuse by the act, not by the bit (B-89)

- [ ] 4b.1 Restate `refusal()` in `lib/set_orch/api/desktop.py` by the ACT: keep every current
  refusal and add the suffixes whose association commonly executes or interprets the file —
  `.jar`, `.appimage`, `.run`, `.jnlp`, `.msi`, installer packages, macro-carrying office
  formats, and `.html`/`.htm`/`.xhtml` for the `file://` origin [REQ: what-must-never-be-handed-over]
- [ ] 4b.2 Make the answer name WHICH rule fired — an association refusal must not report
  itself as an executable-bit refusal [REQ: what-must-never-be-handed-over]
- [ ] 4b.3 Test a 644 `.jar`, `.html` and macro document with NO executable bit: each refused,
  each naming the association. This is the measurement that found B-89, held as a test
  [REQ: what-must-never-be-handed-over]
- [ ] 4b.4 Test that an image, a video, a PDF and a plain document with no executable bit are
  still handed over — the widening must refuse nothing that was already working
  [REQ: what-must-never-be-handed-over]
- [ ] 4b.5 Assert the guard consults NO local desktop association: same input, same verdict,
  on any machine [REQ: what-must-never-be-handed-over]
- [ ] 4b.6 Close `B-89` with the sha [REQ: what-must-never-be-handed-over]

## 5. The panel — rendering by type

- [ ] 5.1 Extend the `Opened` union in `FleetFileView.tsx` with a binary arm carrying the
  media type and size [REQ: the-panel-renders-a-file-by-its-type]
- [ ] 5.2 Render an image by FETCHING the bytes, checking the media type against the panel's
  own allow-list, and building the object URL client-side — never by pointing an `<img>` at
  the endpoint. Scaled to fit the panel without overflowing it, with no save control
  [REQ: the-panel-renders-a-file-by-its-type]
- [ ] 5.2b A PDF is named with its size and handed over, not embedded — the research behind
  this is in design.md's resolved open question
  [REQ: the-panel-renders-a-file-by-its-type]
- [ ] 5.3 Render a stated-type binary as type + size, offering the desktop hand-over
  [REQ: the-panel-renders-a-file-by-its-type]
- [ ] 5.4 Keep the three refusals distinguishable in the panel's own wording — too large, no
  view for this type, unreadable [REQ: what-cannot-be-shown-is-stated-in-the-panel]
- [ ] 5.5 Test that switching from a binary back to a text file restores the editor and its
  save control, with no state left from the image view
  [REQ: the-panel-renders-a-file-by-its-type]
- [ ] 5.6 Confirm nothing of a project reaches browser storage on the new paths — no bytes, no
  media type, no path [REQ: the-panel-renders-a-file-by-its-type]

## 6. The panel — revealing a directory

- [x] 6.1 Implement reveal: expand ancestors, scroll into view, mark the node, open no file
  [REQ: a-directory-can-be-revealed-in-the-structure-pane]
- [x] 6.2 State it in the panel when the revealed directory has nothing beneath it in the
  current listing, mentioning that the listing may be excluding what it holds — never a silent
  no-op [REQ: a-directory-can-be-revealed-in-the-structure-pane]
- [ ] 6.3 Test that a reveal leaves an unsaved edit and the open file untouched
  [REQ: a-directory-can-be-revealed-in-the-structure-pane]

## 7. Look at it, and measure the result rather than the mechanism

- [ ] 7.1 **LOOK AT IT in the browser** against the running dashboard: ctrl-click a `.sh` in a
  terminal and see it open as text; ctrl-click a PNG an agent printed and see the image;
  ctrl-click a directory and see the tree reveal it; confirm `/opsx:ff` in the output carries
  no underline. If the browser cannot be reached this task stays OPEN and the commit says so
  [REQ: the-panel-renders-a-file-by-its-type]
- [ ] 7.2 **LOOK AT IT for a cross-checkout link**: a worktree agent's absolute path into the
  main checkout opens in the panel, and the panel NAMES the checkout it is reading. This also
  closes `fleet-open-external-path` 7.16
  [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor]
- [ ] 7.3 Run the full web unit suite and the Python suite, and compare failures as a SET DIFF
  against a baseline you actually ran — never against a remembered count
  [REQ: file-content-is-served-typed-by-its-bytes]
- [ ] 7.4 Close `B-83`…`B-88` in `openspec/bugs/README.md` with the commit sha, each against
  the "fixed when" check it already names. An entry is closed with evidence, never deleted
  [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor]

## Acceptance Criteria (from spec scenarios)

### A terminal token is recognised as one of two kinds of reference

- [x] AC-1: WHEN the output contains a project-relative path followed by a colon and a number THEN the terminal treats it as a reference to that file at that line [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: a-relative-path-with-a-line-number]
- [x] AC-2: WHEN the output contains an absolute path inside any registered project or a worktree of one THEN it is treated as an internal reference [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: an-absolute-path-inside-a-checkout-the-framework-may-read]
- [x] AC-3: WHEN the output contains an absolute path under no registered checkout THEN it is recognised as a desktop reference [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: an-absolute-path-under-no-known-checkout]
- [x] AC-4: WHEN the output contains `/opsx:ff`, `/dd` or a web route THEN it carries no underline and no tooltip in ordinary reading [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: a-single-segment-absolute-token]
- [x] AC-5: WHEN a path appears inside backticks, bold markers, or both THEN the markers are stripped and the path is recognised [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: a-path-wrapped-in-markdown-emphasis]
- [x] AC-6: WHEN the output contains `docs/x.md:12|` as a table cell THEN the separator is stripped and the reference is `docs/x.md` at line 12 [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: a-path-at-the-end-of-a-table-row]
- [x] AC-7: WHEN a token begins with `~/` THEN it is resolved against the framework account's home and judged as absolute [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: a-home-relative-path]
- [x] AC-8: WHEN exactly one listing path ends with the relative token on a path boundary THEN that file is what the reference names [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: a-relative-token-that-uniquely-suffixes-one-known-file]
- [x] AC-9: WHEN two or more listing paths end with the token and the reader activates it THEN the matches are offered and none is opened until they choose [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: a-relative-token-that-suffixes-more-than-one-known-file]
- [x] AC-10: WHEN the output contains a relative path naming a directory of a readable checkout THEN it is an internal reference to that directory [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: a-relative-directory]
- [x] AC-11: WHEN the output contains `and/or` or `24/7` THEN it is left as ordinary text [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: prose-that-merely-contains-a-slash]
- [x] AC-12: WHEN a relative token appears with no project context THEN it is left as ordinary text [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: a-relative-token-with-no-project-context]

### What the internal editor can open, opens in the internal editor

- [x] AC-13: WHEN a person activates a relative path that is a file of the agent's worktree THEN the file view opens it, reading that worktree [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor, scenario: a-file-of-the-agents-worktree]
- [ ] AC-14: WHEN a person activates a shell script or other executable text file inside a served checkout THEN the file view opens it as text and the desktop route is not involved [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor, scenario: an-executable-text-file]
- [x] AC-15: WHEN a worktree agent prints an absolute path into the main checkout and a person activates it THEN the file view opens the main checkout's file and names that checkout [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor, scenario: a-file-of-the-main-checkout-printed-by-a-worktree-agent]
- [x] AC-16: WHEN the activated path lies inside another registered project THEN the file view opens it and names that project [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor, scenario: a-file-of-another-registered-project]
- [ ] AC-17: WHEN the file view is reading a checkout other than the project root THEN the panel names that checkout [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor, scenario: the-panel-names-the-checkout-it-is-reading]
- [ ] AC-18: WHEN a file read from a worktree is edited and saved THEN it is written back to that worktree [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor, scenario: a-save-goes-back-where-the-file-came-from]
- [ ] AC-19: WHEN the activated reference names a path under no registered checkout THEN it is handed to the desktop, unchanged from today [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor, scenario: a-path-under-no-known-checkout]
- [ ] AC-20: WHEN the file endpoints are asked for a non-prunable worktree of a known project THEN they serve it with the same confinement, limits and refusals [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor, scenario: a-worktree-of-a-known-project-may-be-read]
- [ ] AC-21: WHEN the file endpoints are asked for a directory that is neither a known root nor a worktree of one THEN they refuse it [REQ: what-the-internal-editor-can-open-opens-in-the-internal-editor, scenario: an-unrelated-directory-is-still-refused]

### Activating a desktop reference hands it to the desktop

- [ ] AC-22: WHEN a person activates an absolute path under no registered checkout THEN it is handed to the desktop and nothing opens inside the dashboard [REQ: activating-a-desktop-reference-hands-it-to-the-desktop, scenario: the-reader-activates-an-external-path]
- [ ] AC-23: WHEN a person clicks a recognised reference without the modifier THEN the click is the terminal's and nothing opens [REQ: activating-a-desktop-reference-hands-it-to-the-desktop, scenario: a-plain-click-still-belongs-to-the-terminal]
- [ ] AC-24: WHEN a desktop reference names something the desktop would run or interpret THEN it is refused and nothing is started — this change widens that list and relaxes no part of it [REQ: activating-a-desktop-reference-hands-it-to-the-desktop, scenario: the-desktop-guards-refuse-at-least-as-much-as-before]

### Activating a directory reveals it in the panel's structure

- [x] AC-25: WHEN a person activates a relative path naming a directory of the checkout THEN the file view opens with that node expanded and scrolled into view, and no desktop application launches [REQ: activating-a-directory-reveals-it-in-the-structure-pane, scenario: a-directory-of-the-agents-checkout]
- [x] AC-26: WHEN the activated directory has no files under it in the listing THEN the panel says so where the reader is standing [REQ: activating-a-directory-reveals-it-in-the-structure-pane, scenario: a-directory-with-nothing-beneath-it-in-the-listing]
- [x] AC-27: WHEN the activated directory lies under no registered checkout THEN it is handed to the desktop as today [REQ: activating-a-directory-reveals-it-in-the-structure-pane, scenario: a-directory-under-no-known-checkout]

### One file's content can be read, typed by its bytes

- [ ] AC-28: WHEN a readable text file inside a served checkout is requested THEN the endpoint returns its content and a content identity [REQ: file-content-is-served-typed-by-its-bytes, scenario: a-text-file-is-returned-with-its-identity]
- [ ] AC-29: WHEN the requested file decodes as UTF-8 and has an executable bit THEN it is returned as text and the bit changes nothing [REQ: file-content-is-served-typed-by-its-bytes, scenario: a-text-file-carrying-an-executable-bit]
- [ ] AC-30: WHEN the requested file has no suffix or an unknown one and decodes as UTF-8 THEN it is returned as text [REQ: file-content-is-served-typed-by-its-bytes, scenario: a-text-file-with-no-extension]
- [ ] AC-31: WHEN the file does not decode and its media type is one served for rendering THEN the endpoint returns its bytes with that media type [REQ: file-content-is-served-typed-by-its-bytes, scenario: a-renderable-binary-is-served-as-bytes]
- [ ] AC-32: WHEN the file is neither decodable text nor renderable THEN the refusal names the media type and the size and returns no partial content [REQ: file-content-is-served-typed-by-its-bytes, scenario: a-binary-that-cannot-be-rendered-names-its-type]
- [ ] AC-33: WHEN the file is larger than the cap THEN the refusal states the size and the cap and is distinguishable from the type refusal [REQ: file-content-is-served-typed-by-its-bytes, scenario: a-file-too-large-to-serve-is-refused-with-its-size]
- [ ] AC-34: WHEN any of these answers is served THEN the path was confined by the same verdict and refusal as before [REQ: file-content-is-served-typed-by-its-bytes, scenario: the-confinement-is-unchanged]

### What cannot be shown is stated in the panel

- [ ] AC-35: WHEN the endpoint refuses a file as too large, as a type with no view, or as unreadable THEN the panel states the reason where the content would be [REQ: what-cannot-be-shown-is-stated-in-the-panel, scenario: a-file-the-endpoint-refused]
- [ ] AC-36: WHEN the endpoint refuses a file for exceeding the size cap THEN the panel states that, naming the file, its size and the cap [REQ: what-cannot-be-shown-is-stated-in-the-panel, scenario: a-file-the-endpoint-refused-as-too-large]
- [ ] AC-37: WHEN the endpoint answers with a media type the panel has no view for THEN the panel states the type and size and offers the desktop hand-over [REQ: what-cannot-be-shown-is-stated-in-the-panel, scenario: a-file-of-a-type-the-panel-cannot-render]
- [ ] AC-38: WHEN an opened file has no content THEN the panel shows an empty file and says so [REQ: what-cannot-be-shown-is-stated-in-the-panel, scenario: an-empty-file-is-not-a-failure]

### The panel renders a file by its type

- [ ] AC-39: WHEN the endpoint answers with text THEN the editor opens it with wrap, marker and save behaviour unchanged [REQ: the-panel-renders-a-file-by-its-type, scenario: a-text-file]
- [ ] AC-40: WHEN the endpoint answers with an image media type THEN the panel displays it scaled to fit without overflowing, and offers no save control [REQ: the-panel-renders-a-file-by-its-type, scenario: an-image]
- [ ] AC-41: WHEN the activated file is a shell script inside a served checkout THEN it opens in the editor as text, editable and saveable [REQ: the-panel-renders-a-file-by-its-type, scenario: a-shell-script]
- [ ] AC-42: WHEN the endpoint refuses a file as a type the panel cannot render THEN the panel names type and size, offers the hand-over, and shows no editor [REQ: the-panel-renders-a-file-by-its-type, scenario: a-binary-with-no-view]
- [ ] AC-43: WHEN the reader opens an image and then a text file THEN the editor returns with its save control and no image state remains [REQ: the-panel-renders-a-file-by-its-type, scenario: switching-from-a-binary-back-to-text]

### A directory can be revealed in the structure pane

- [ ] AC-44: WHEN a directory of the opened checkout is revealed THEN its ancestors expand, the node scrolls into view and is marked, and no file opens [REQ: a-directory-can-be-revealed-in-the-structure-pane, scenario: a-directory-that-has-files-beneath-it]
- [ ] AC-45: WHEN the revealed directory has no files under it in the listing THEN the panel states that and mentions the listing may be excluding what it holds [REQ: a-directory-can-be-revealed-in-the-structure-pane, scenario: a-directory-the-listing-has-nothing-beneath]
- [ ] AC-46: WHEN a directory is revealed while the opened file has unsaved edits THEN the edits are untouched and the file stays open [REQ: a-directory-can-be-revealed-in-the-structure-pane, scenario: revealing-does-not-disturb-an-unsaved-edit]

### Added after the 2026-08-27 research pass

- [x] AC-47: WHEN a person holds the modifier over a path-shaped token the framework could not place THEN it becomes activatable [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: a-low-confidence-token-while-the-modifier-is-held]
- [x] AC-48: WHEN the token carries characters no path may hold, such as a route parameter's brackets THEN no modifier makes it a link [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: a-token-that-is-not-path-shaped-at-all]
- [x] AC-49: WHEN a row, a token, or the reference count on a row exceeds the limits THEN recognition stops for that row [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference, scenario: a-line-a-token-or-a-row-count-beyond-the-recognisers-limits]
- [ ] AC-50: WHEN any byte response is served THEN it carries nosniff and an attachment disposition [REQ: file-content-is-served-typed-by-its-bytes, scenario: the-bytes-are-not-served-as-something-to-render]
- [ ] AC-51: WHEN the determined media type is off the allow-list THEN no bytes are served and the answer is the naming refusal [REQ: file-content-is-served-typed-by-its-bytes, scenario: a-media-type-off-the-allow-list]
- [ ] AC-52: WHEN the activated file is a PDF THEN the panel names it with its size and offers the hand-over, embedding no viewer [REQ: the-panel-renders-a-file-by-its-type, scenario: a-pdf]
- [ ] AC-53: WHEN the fetched bytes would be interpreted as a renderable document by a browser left to itself THEN nothing renders them [REQ: the-panel-renders-a-file-by-its-type, scenario: a-file-whose-bytes-claim-to-be-a-document]

### What must never be handed over (B-89)

- [ ] AC-54: WHEN the activated path names a file with an executable bit THEN it is refused and the answer names the reason [REQ: what-must-never-be-handed-over, scenario: an-executable-file]
- [ ] AC-55: WHEN the activated path names a `.desktop` file THEN it is refused whatever its permissions are [REQ: what-must-never-be-handed-over, scenario: a-desktop-entry]
- [ ] AC-56: WHEN the activated path names a `.jar`, `.appimage`, `.run`, `.jnlp` or installer package with NO executable bit THEN it is refused, naming the association rather than the permissions [REQ: what-must-never-be-handed-over, scenario: an-archive-a-runtime-executes]
- [ ] AC-57: WHEN the activated path names an HTML file or a macro-carrying office document with no executable bit THEN it is refused [REQ: what-must-never-be-handed-over, scenario: a-document-that-carries-active-content]
- [ ] AC-58: WHEN the activated path names an image, video, PDF or plain document not on the list THEN it is handed over exactly as before [REQ: what-must-never-be-handed-over, scenario: an-ordinary-file-is-still-handed-over]
- [ ] AC-59: WHEN the activated path does not exist THEN it is refused and no handler starts [REQ: what-must-never-be-handed-over, scenario: a-path-that-is-not-there]
- [ ] AC-60: WHEN the request carries a path that is not absolute THEN it is refused [REQ: what-must-never-be-handed-over, scenario: a-relative-path]
- [ ] AC-61: WHEN the endpoint decides whether to refuse a path THEN it decides from the path alone, never from this machine's associations [REQ: what-must-never-be-handed-over, scenario: the-refusal-does-not-query-the-local-desktop]
