## Why

Activating a video, image or audio path in a fleet terminal fails on the most common media
setup there is: an external drive. Measured 2026-10-19 on a live report, a rendered `.mp4`
printed by an agent:

- the path was under a registered checkout (a project registered at the account's home), so
  the terminal sent it to the internal file view, which cannot play a video and, because the
  directory was a symlink out of that checkout, refused it;
- the view's own "open on the desktop" button was then refused too, because the file carried
  an executable bit. The drive is exFAT, which stores no Unix permissions: **844 of 844 files
  on it read as executable**, so every file on it is refused by the desktop guard whatever it is.

The owner's request: a media file activated in the terminal opens directly in the desktop's
player or viewer, without going through the editor first.

## What Changes

- **Routing** (`terminal-file-links`): a reference whose name ends in one of a fixed, measured
  list of media suffixes (video, audio, raster image, PDF) is handed to the desktop, also when it
  lies inside a checkout the file view serves. Everything else routes exactly as before.
- **Guard** (`desktop-open`): for that same list, the executable bit is not consulted, on the
  platform where the measurement was made (Linux). The suffix rules, the launcher rules, the
  local-page rule and the resolve-before-judging order are unchanged; a symlink named like a
  video that points at a program is still judged by its target. macOS keeps the executable-bit
  refusal until it is measured there.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `terminal-file-links`: media references go to the desktop from inside a checkout too.
- `desktop-open`: the executable bit is not a reason to refuse a measured media suffix on Linux.

## Impact

- `lib/set_orch/api/desktop.py` (Layer 1): `_MEDIA_SUFFIXES`, one condition in `refusal()`.
- `web/src/lib/fleetFiles.ts`: `MEDIA_SUFFIXES`, the media branch in `terminalTarget`.
- Tests: `tests/unit/test_desktop_open_api.py`, `web/tests/unit/fleetFiles.test.ts`, and a test
  holding the two suffix lists equal.
- Behaviour change visible to the reader: a raster image inside a project, which used to be
  drawn in the file view, now opens in the desktop's image viewer when activated from a terminal.
  The file view still draws an image opened from its own tree.
