## 1. Guard (Layer 1, `lib/set_orch/api/desktop.py`)

- [x] 1.1 `_MEDIA_SUFFIXES` with the measured list; in `refusal()` the executable-bit check is skipped for a resolved target ending in one of them when the opener is `xdg-open` [REQ: what-must-never-be-handed-over]
- [x] 1.2 Tests in `tests/unit/test_desktop_open_api.py`: a 755 `.mp4` opens on Linux; a link `clip.mp4` → an executable without a media suffix is refused; a 755 `.mp4` is refused on macOS; each proved to fail with 1.1 reverted where it should [REQ: what-must-never-be-handed-over]

## 2. Routing (`web/src/lib/fleetFiles.ts`)

- [x] 2.1 `MEDIA_SUFFIXES` and the media branch in `terminalTarget`: a `file` target whose path ends in a media suffix becomes a `desktop` target with the absolute path [REQ: a-file-of-a-readable-checkout-opens-in-the-internal-editor]
- [x] 2.2 Tests in `web/tests/unit/fleetFiles.test.ts`: an absolute and a relative media path inside a checkout route to the desktop; `.ts` and `.png.ts`-style names do not [REQ: a-file-of-a-readable-checkout-opens-in-the-internal-editor]
- [x] 2.3 A Python test that reads `MEDIA_SUFFIXES` from `fleetFiles.ts` and asserts it equals `_MEDIA_SUFFIXES` [REQ: what-must-never-be-handed-over]

## 3. Verification

- [x] 3.1 `pnpm build` and `tsc -b` in `web/` clean; desktop tests 42/42; web unit suite 1574/1580 — the 3 repeatable failures (`designDrift`, `fleetArrangement` unknown-state, `fleetTileClick` body click) fail identically with `fleetFiles.ts` at HEAD, and the other failures move between runs in files that do not import `fleetFiles` (flaky)
- [x] 3.2 Restart set-web, then in the browser Ctrl+click a media path in a fleet terminal and see it handed to the desktop — measured as one `POST /api/desktop/open` from the page, `desktop_open: handed over` in the journal, and `mpv` started with the file; the file view did not open. The success status clears itself after 4 s and was not caught on screen; if the browser cannot be reached this task stays open [REQ: a-file-of-a-readable-checkout-opens-in-the-internal-editor]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a 755 `.mp4` is activated on Linux THEN it is handed to the desktop [REQ: what-must-never-be-handed-over, scenario: a-media-file-carrying-an-executable-bit]
- [x] AC-2: WHEN a link `clip.mp4` points at an executable without a media suffix THEN it is refused naming the executable bit [REQ: what-must-never-be-handed-over, scenario: a-link-named-like-a-video-that-points-at-a-program]
- [x] AC-3: WHEN a 755 `.mp4` is activated on macOS THEN it is refused naming the executable bit [REQ: what-must-never-be-handed-over, scenario: the-media-exception-is-not-taken-on-an-unmeasured-platform]
- [x] AC-4: WHEN a `.mp4` or `.png` inside a served checkout is activated THEN it is handed to the desktop and the file view is not opened [REQ: a-file-of-a-readable-checkout-opens-in-the-internal-editor, scenario: a-media-file-inside-a-checkout-goes-to-the-desktop]
- [x] AC-5: WHEN a `.ts` file of the checkout is activated THEN the file view opens it [REQ: a-file-of-a-readable-checkout-opens-in-the-internal-editor, scenario: a-typescript-file-is-not-media]
