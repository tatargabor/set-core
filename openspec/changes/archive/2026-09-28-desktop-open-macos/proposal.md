## Why

`POST /api/desktop/open` refuses every request on macOS. The opener is the constant
`xdg-open` (`lib/set_orch/api/desktop.py:55`), which does not exist there, so the endpoint
answers `501 no desktop handler available (xdg-open not found)` — measured 2026-09-25 from a
fleet terminal on a Mac mini, activating `~/Downloads/<name>.pdf`. The framework now runs on
macOS as well as Linux, and a feature that answers "not on this platform" for a whole platform
is not a refusal, it is an absence.

Wiring the opener is the smaller half. The refusal list that decides what may be handed over
was measured on a Linux desktop and names Linux launcher classes; **macOS has its own, and one
of them slips through a check that is correct on Linux**. A `.app` is a *directory*, and the
executable-bit rule deliberately does not apply to directories (every traversable directory
has the bit), so with the opener wired up and nothing else changed, `open Foo.app` would start
an application through an endpoint whose entire contract is that it opens documents and never
runs programs.

## What Changes

- The opener is resolved per platform instead of being a constant: `open` on macOS (`darwin`),
  `xdg-open` elsewhere. The refusal when the platform's opener is absent stays exactly as it
  is — the endpoint still reports rather than guessing at a second candidate.
- The refusal list gains the macOS launcher classes, each measured on this machine with
  `mdls -name kMDItemContentType`:
  - `.app` → `com.apple.application-bundle` — an application, and a directory, so it is added
    to the **launcher** class rather than relying on any permission check.
  - `.command` → `com.apple.terminal.shell-script` — Terminal executes it.
  - `.terminal` → `com.apple.terminal.settings` — opens a Terminal profile, which can carry a
    command to run.
  - `.dmg` → `com.apple.disk-image-udif` — opening one mounts it, which is the installer class
    `.pkg`/`.deb`/`.snap` already occupy.
- `.workflow` is deliberately **not** added: the same probe returned a dynamic UTI
  (`dyn.ah62d4rv4ge81s55wrrxg2551`), i.e. nothing is registered for it on this machine, and
  this module's own rule is that the list is widened by measurement, never by plausibility.
- The message on an unsupported platform names the opener that platform actually wants, so the
  reader is not sent to install `xdg-open` on a Mac.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `desktop-open`: the endpoint is no longer single-platform — the opener is whatever the host
  platform's is, and the "what must never be handed over" list is platform-complete for both
  supported platforms rather than for Linux only.

## Impact

- `lib/set_orch/api/desktop.py` — opener resolution and the refusal suffix lists.
- `tests/unit/test_desktop_open_api.py` — the platform branch, and the new refusals. The
  existing tests patch `Popen`, so nothing starts for real; the new ones must hold on **both**
  platforms (a macOS-only assertion would silently pass as a skip on the Linux machines this
  framework also runs on).
- No API shape change: same route, same request body, same answer keys. A caller that works
  today keeps working.
- Fleet terminal path activation is the only caller and needs no change.
