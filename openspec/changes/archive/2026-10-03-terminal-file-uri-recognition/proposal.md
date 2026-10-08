## Why

An agent that builds a page prints its address in the desktop's own spelling — a `file:` URI — and the
terminal turned that spelling into dead text: the recogniser filtered every token containing `://` out of
both routes, so nothing was offered, nothing was underlined, and activating it did nothing. Measured live
(2026-10-03, B-156): the endpoint itself worked — the same page opened through the file view's desktop
button — only the recogniser never offered the token. Separately, the same live session measured that
while the agent's TUI holds mouse tracking, xterm hands every mouse event to the pty and never activates
a link, so even a correctly drawn link (a plain path included) does nothing at click time — the state
`terminal-file-links`' own "reachable while the agent holds the mouse" requirement exists for.

## What Changes

- A `file:` URI is recognised as the path it names: the recogniser translates it (local host only,
  percent-decoded, another host refused) and offers it through the same two routes as the bare path —
  the file view when a served checkout contains it, the desktop hand-over otherwise. The refusal lists
  of `desktop-open` are untouched: they rule on the PATH either way.
- A confirmed reference under the pointer is activated on Ctrl+click by the terminal itself, in the
  capture phase, in BOTH mouse-tracking states — implementing the existing mouse-reachability
  requirement instead of leaving the click to whichever layer the TUI's mode happens to leave alive.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `terminal-file-links`: the recognition requirement gains the `file:` URI spelling of a path, and the
  mouse-reachability requirement's mouse route is stated as working in both tracking states rather than
  depending on the TUI's mode.

## Impact

- `web/src/lib/fleetFiles.ts` — `fileUriPath`, `referenceAtColumn`, the `desktopReference` and
  `terminalTarget` candidate pipelines.
- `web/src/components/FleetTerminal.tsx` — the capture-phase activation.
- `web/tests/unit/fleetFiles.test.ts` — the recognition and column cases.
- No endpoint, contract-field or refusal-list change; `desktop-open` is untouched.
