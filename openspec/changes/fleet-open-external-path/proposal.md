## Why

An agent prints the absolute path of what it just produced — a screenshot, a report, a
downloaded file — and that path is almost never inside the project it is working in. Today
the terminal deliberately leaves such a token as plain text: the file-link route ends at the
project root, because the only thing it can do with a path is open it in the dashboard's own
file view, and that view may read nothing outside a registered project.

The result is the failure the file-link work already named once and did not close: a
reference the terminal renders and the reader cannot follow. Reported 2026-08-26 against a
live fleet terminal — two `/tmp/claude-chrome-screenshots-*/screenshot-*.jpg` paths printed
beside a URL that *was* clickable, and reaching them meant selecting the text by hand out of
a fixed grid.

The missing route is not "read it in the dashboard". It is "hand it to the desktop", which is
what `xdg-open` is for and what the reader asked for by name.

## What Changes

- **New**: an endpoint that hands ONE absolute path to the desktop's default application
  (`xdg-open` on Linux), and refuses everything it must not run.
  - Refused: a relative path, a path that does not exist, a `.desktop` file, and any file
    carrying an executable bit. `xdg-open` would *run* those rather than open them, and the
    text it came from was written by whatever the agent ran.
  - The framework never opens anything on its own: the endpoint answers only a request a
    person's activation produced.
  - It reads no content and persists nothing — it does not become a second file-read path.
- **Modified**: the terminal's file-link rule gains a second destination. A path-shaped
  absolute token inside the project keeps opening in the file view, unchanged; one outside it
  is now offered as a link that hands the path to the desktop.
- **Modified**: activating a link that turns out to be unopenable — no such file, an
  executable, a refusal — says so on the terminal's status row. There is deliberately NO
  existence probe: a "does this path exist" endpoint would be a filesystem oracle over the
  whole machine, which is exactly what `project-file-access` refuses to become. The cost is
  accepted and stated — some underlined tokens will fail on activation, and they will say why.

## Capabilities

### New Capabilities
- `desktop-open`: handing one path to the desktop's default application, and the refusals
  that keep it from becoming a way to execute something.

### Modified Capabilities
- `terminal-file-links`: a path outside the project root is no longer ordinary text — it
  becomes a link with a different destination, and an activation that cannot be honoured
  reports its reason.

## Impact

- `lib/set_orch/api/` — a new router for the open endpoint, registered beside the existing
  fleet routers. No change to `files.py`'s guard or its `_known_roots` contract.
- `web/src/lib/fleetFiles.ts` — the decision "is this token an out-of-project absolute path"
  lands here, beside `fileReference`, so it is measurable without a browser.
- `web/src/components/FleetTerminal.tsx` — the link provider offers the second kind of link;
  the existing status row carries the failure message.
- `web/src/pages/Fleet.tsx` — passes the activation through to the endpoint.
- No change to the URL handling (`terminalLinkTarget`) and no change to what the file view
  may read.
