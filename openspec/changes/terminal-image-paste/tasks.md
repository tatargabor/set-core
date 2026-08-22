## 1. The store, server side

- [x] 1.1 New module `lib/set_orch/api/paste.py` with a header stating what it must never become — a project writer, a cache read over HTTP, a file manager — and why it is not part of `files.py` [REQ: pasted-content-is-stored-outside-every-project-tree]
- [x] 1.2 The store root: `SET_TOOLS_DATA_DIR/paste/`, created on first use, resolved through `lib/set_orch/paths.py` rather than a second literal [REQ: pasted-content-is-stored-outside-every-project-tree]
- [x] 1.3 The four bounds in ONE named place: per-item 8 MB, total 256 MB, max age 7 days, accepted types [REQ: only-images-and-only-within-a-bound]
- [x] 1.4 Sniff the type from the magic bytes (PNG, JPEG, GIF, WebP); the declared type is never trusted and a mismatch refuses [REQ: only-images-and-only-within-a-bound]
- [x] 1.5 Name the file `<sha256-of-bytes>.<sniffed-ext>`; the caller's file name is DISCARDED, not sanitised, and never reaches the path [REQ: the-stored-name-is-derived-never-taken-from-the-caller]
- [x] 1.6 Sweep on every store operation: drop entries past max age, then oldest-first while the total exceeds the ceiling; computed from disk so nothing survives a period when the framework was stopped [REQ: the-store-is-bounded-and-its-entries-expire]
- [x] 1.7 Refusals name the rule that refused them (type, size, ceiling) and write nothing [REQ: only-images-and-only-within-a-bound]
- [x] 1.8 Log the SHAPE only — content type, byte count, outcome, refusing rule — never the bytes, the caller's name or the stored name; copy the pattern from `db_safety.py` [REQ: nothing-about-the-content-is-persisted-or-logged]
- [x] 1.9 Route `POST /api/fleet/paste`, registered in `lib/set_orch/api/__init__.py` beside `files_router` and BEFORE the `/api/{project}/...` families, since that order is load-bearing [REQ: pasted-content-is-stored-outside-every-project-tree]

## 2. The store's tests

- [x] 2.1 Test file `tests/unit/test_paste_api.py` following `test_files_api.py`: real `tmp_path`, `TestClient(create_app(web_dist_dir=None))`, the store root patched on the module under test [REQ: pasted-content-is-stored-outside-every-project-tree]
- [x] 2.2 A stored image lands under the store root and NOT under any project root or worktree — asserted by walking the project tree and finding it unchanged [REQ: pasted-content-is-stored-outside-every-project-tree]
- [x] 2.3 A caller-supplied name containing `..`, a separator and a control character changes nothing about the resulting path [REQ: the-stored-name-is-derived-never-taken-from-the-caller]
- [x] 2.4 The same bytes twice give the same usable path [REQ: the-stored-name-is-derived-never-taken-from-the-caller]
- [x] 2.5 A declared `image/png` carrying non-image bytes is refused [REQ: only-images-and-only-within-a-bound]
- [x] 2.6 Over-size and unsupported-type refusals each name their own rule, and write nothing [REQ: only-images-and-only-within-a-bound]
- [x] 2.7 Expiry: an entry back-dated past the max age is gone after the next store call, with no error [REQ: the-store-is-bounded-and-its-entries-expire]
- [x] 2.8 Ceiling: filling past the total evicts oldest-first; an item that still does not fit is refused with the ceiling named [REQ: the-store-is-bounded-and-its-entries-expire]
- [x] 2.9 A log-capturing test asserts the emitted records carry no caller name, no stored name and no content-derived text [REQ: nothing-about-the-content-is-persisted-or-logged]

## 3. The panel, browser side

- [x] 3.1 A decision function in `web/src/lib/fleetTerminal.ts` that, given a `ClipboardEvent`'s items, returns the image to upload or `null` — text present means `null` [REQ: text-paste-keeps-its-existing-behaviour]
- [x] 3.2 Wire a `paste` listener in `FleetTerminal.tsx` that consults it, leaves every text paste untouched, and only then uploads [REQ: text-paste-keeps-its-existing-behaviour]
- [x] 3.3 On success write `"<absolute path> "` to the pty as ONE binary frame on the existing socket — the same encoder `onData` uses — with no newline [REQ: a-pasted-image-reaches-the-agent-as-a-path-it-can-open]
- [x] 3.4 In-flight state visible in the header while the upload is on its way; the terminal stays usable [REQ: a-failed-paste-is-stated-never-silent]
- [x] 3.5 Failure and refusal shown in the header with the reason given, and NOTHING written to the pty [REQ: a-failed-paste-is-stated-never-silent]
- [x] 3.6 A request timeout, so a hung upload becomes a stated failure rather than a permanent "in flight" [REQ: a-failed-paste-is-stated-never-silent]
- [x] 3.7 Nothing about the image, its name or its path is written to `localStorage`, `sessionStorage`, IndexedDB or a cache, and the bytes are dropped once the request is answered [REQ: nothing-about-the-pasted-image-is-kept-in-the-browser]

## 4. The panel's tests

- [x] 4.1 A text-only paste uploads NOTHING — asserted explicitly, because a regression that uploads on every paste would pass every image-only test [REQ: text-paste-keeps-its-existing-behaviour]
- [x] 4.2 A mixed text+image paste is treated as text and uploads nothing [REQ: text-paste-keeps-its-existing-behaviour]
- [x] 4.3 An image-only paste uploads once and writes exactly `"<path> "` to the socket — asserted on the bytes sent, and asserted to contain no `\n` or `\r` [REQ: a-pasted-image-reaches-the-agent-as-a-path-it-can-open]
- [x] 4.4 A refusal and a timeout each render a stated failure and send zero bytes to the socket [REQ: a-failed-paste-is-stated-never-silent]
- [x] 4.5 After a paste, the browser storages are empty of anything about it [REQ: nothing-about-the-pasted-image-is-kept-in-the-browser]
- [x] 4.6 Mutation-check every new test: break the line it guards, watch it go red, restore with a file copy and re-grep the file to prove the restore — never `git checkout`, and clear `__pycache__` between python mutations [REQ: a-pasted-image-reaches-the-agent-as-a-path-it-can-open]

## 5. Verification that a passing suite cannot give

- [ ] 5.1 **STILL OPEN — the browser could not be reached: the endpoint needs a `set-web` restart, which the user declined for now (it kills a running sentinel).** Look at it in the browser, on a live agent terminal: paste a real screenshot with the real key and watch the path arrive. A structural count proves the mechanism ran, not that the result is right [REQ: a-pasted-image-reaches-the-agent-as-a-path-it-can-open]
- [ ] 5.2 Drive it with the key a reader has, not a synthetic `ClipboardEvent` — the defect this whole change came from was measured by a synthetic paste that the reader could never have produced [REQ: a-pasted-image-reaches-the-agent-as-a-path-it-can-open]
- [ ] 5.3 Trigger a real refusal (oversize) in the browser and read the message on screen [REQ: a-failed-paste-is-stated-never-silent]
- [x] 5.4 `npx tsc -b` in `web/` (`--noEmit` is blind here), the full web unit suite, and the python set-diff baseline from `CLAUDE.md` with the three import roots and the leak assertion [REQ: pasted-content-is-stored-outside-every-project-tree]
- [x] 5.5 If the browser cannot be reached, tasks 5.1–5.3 stay OPEN and say so in the commit — an unverifiable screen is a known unknown [REQ: a-failed-paste-is-stated-never-silent]

## Acceptance Criteria (from spec scenarios)

### terminal-image-paste

- [x] AC-1: WHEN the reader pastes content whose types include an `image/*` entry THEN the bytes are sent, the stored absolute path plus one space reaches the pty, and no newline and nothing else is written [REQ: a-pasted-image-reaches-the-agent-as-a-path-it-can-open, scenario: an-image-is-pasted-into-a-focused-terminal]
- [x] AC-2: WHEN the path has been typed THEN the agent has not been asked to act and the line is still the reader's to edit or discard [REQ: a-pasted-image-reaches-the-agent-as-a-path-it-can-open, scenario: the-reader-decides-when-it-is-sent]
- [x] AC-3: WHEN the pasted content is text only THEN the text reaches the pty exactly as today and nothing is uploaded [REQ: text-paste-keeps-its-existing-behaviour, scenario: a-plain-text-paste]
- [x] AC-4: WHEN the paste offers both `text/plain` and `image/*` THEN the text is used, the image ignored, and nothing uploaded [REQ: text-paste-keeps-its-existing-behaviour, scenario: a-paste-carrying-both-text-and-an-image]
- [x] AC-5: WHEN the upload is refused THEN the panel shows the refusal and its reason and the pty receives nothing [REQ: a-failed-paste-is-stated-never-silent, scenario: the-framework-refuses-the-image]
- [x] AC-6: WHEN the upload fails or times out THEN the panel says the image was not sent and the pty receives nothing [REQ: a-failed-paste-is-stated-never-silent, scenario: the-upload-does-not-complete]
- [x] AC-7: WHEN an upload is in flight THEN the panel shows it and the terminal remains usable [REQ: a-failed-paste-is-stated-never-silent, scenario: while-the-image-is-on-its-way]
- [x] AC-8: WHEN a paste has been handled THEN no browser storage holds the image, its name or its path, and a reload recovers nothing [REQ: nothing-about-the-pasted-image-is-kept-in-the-browser, scenario: after-a-paste]

### paste-store

- [x] AC-9: WHEN an image is accepted THEN it is written under the framework's own per-user data root, the response names its absolute path, and no project or worktree path was created or modified [REQ: pasted-content-is-stored-outside-every-project-tree, scenario: an-accepted-image-is-stored]
- [x] AC-10: WHEN a request tries to influence where the file is written THEN the framework decides alone and the suggestion is ignored [REQ: pasted-content-is-stored-outside-every-project-tree, scenario: the-store-cannot-be-redirected-into-a-project]
- [x] AC-11: WHEN the upload carries a file name THEN the stored path does not contain it, and separators, `..` or control characters change nothing [REQ: the-stored-name-is-derived-never-taken-from-the-caller, scenario: a-file-name-arrives-with-the-content]
- [x] AC-12: WHEN identical bytes are stored twice THEN both requests answer with a usable path [REQ: the-stored-name-is-derived-never-taken-from-the-caller, scenario: the-same-image-pasted-twice]
- [x] AC-13: WHEN the content is an accepted image type THEN it is stored [REQ: only-images-and-only-within-a-bound, scenario: an-accepted-type]
- [x] AC-14: WHEN the content is not an accepted image type THEN it is refused naming the type, and nothing is written [REQ: only-images-and-only-within-a-bound, scenario: a-refused-type]
- [x] AC-15: WHEN the content exceeds the per-item limit THEN it is refused naming the limit and the size, and nothing is written [REQ: only-images-and-only-within-a-bound, scenario: content-over-the-size-limit]
- [x] AC-16: WHEN the declared type says image and the bytes are not THEN it is refused and nothing is written [REQ: only-images-and-only-within-a-bound, scenario: the-declared-type-and-the-bytes-disagree]
- [x] AC-17: WHEN a stored entry is older than the maximum age THEN it is removed on the next use of the store, and its absence is not reported as an error [REQ: the-store-is-bounded-and-its-entries-expire, scenario: an-entry-outlives-the-maximum-age]
- [x] AC-18: WHEN storing would take the store past its ceiling THEN oldest entries are removed until it fits, and an item that still does not fit is refused with the ceiling named [REQ: the-store-is-bounded-and-its-entries-expire, scenario: the-store-reaches-its-ceiling]
- [x] AC-19: WHEN the framework starts after being stopped THEN expiry is applied from the entries on disk and nothing survives merely because nothing was running [REQ: the-store-is-bounded-and-its-entries-expire, scenario: the-framework-was-not-running]
- [x] AC-20: WHEN an upload is stored THEN the log line carries content type, byte count and outcome, and carries neither the bytes, a caller-supplied name, nor the stored file name [REQ: nothing-about-the-content-is-persisted-or-logged, scenario: a-stored-image-is-logged]
- [x] AC-21: WHEN an upload is refused THEN the log line names the refusing rule and carries nothing derived from the content [REQ: nothing-about-the-content-is-persisted-or-logged, scenario: a-refused-image-is-logged]
