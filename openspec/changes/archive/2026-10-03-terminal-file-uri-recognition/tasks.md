<!--
Implementation and verification were completed in the same session that measured the
defect (B-156); each task carries its own evidence. Requirements slugs are the two
MODIFIED requirements of specs/terminal-file-links/spec.md.
-->

## 1. Recognition — the `file:` URI spelling of a path

- [x] 1.1 `fileUriPath` in `web/src/lib/fleetFiles.ts`: translate a `file:` URI to its local absolute path — host empty or `localhost` only, absolute pathname, percent-decoded, any other form left as text. [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 1.2 Wire the translation into both routes' candidate pipelines (`terminalTarget`, `desktopReference`) so the URI reaches the same classification as the bare path. [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 1.3 Unit tests: URI inside a served checkout → file reference; outside → desktop reference; another host → null; undecodable escape → null; line number dropped; percent-decoded name. Stash-and-rerun measured: 4 of these fail without the lib change. [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]

## 2. Reachability — the gesture in both mouse-tracking states

- [x] 2.1 `referenceAtColumn` in `web/src/lib/fleetFiles.ts`: the click-side half of the recogniser — one row, one column, one verdict — measurable without a browser. [REQ: the-reference-is-reachable-while-the-agent-holds-the-mouse]
- [x] 2.2 Capture-phase mousedown/mouseup on the terminal host in `FleetTerminal.tsx`: with CTRL held and a confirmed reference under the pointer, prevent, stop, and activate through the same `act` the provider uses; 600 ms same-target debounce as the double-fire guard; every other case returns untouched. [REQ: the-reference-is-reachable-while-the-agent-holds-the-mouse]
- [x] 2.3 Unit tests for the column verdict: token coverage, boundary columns, prose rows. [REQ: the-reference-is-reachable-while-the-agent-holds-the-mouse]

## 3. Verification — the running system

- [x] 3.1 Type check clean (`tsc -b`); full unit suite set-diffed against a stashed baseline (8 vs 9 vs 6 failures across three runs, wobbling composition — pre-existing flake in `fleetSurface`/`fleetArrangement`; `designDrift` and `fleetTileClick` fail identically in every run including the baseline). [REQ: a-terminal-token-is-recognised-as-one-of-two-kinds-of-reference]
- [x] 3.2 Live end-to-end against the running dashboard: Ctrl+click on the real transcript's `file:///…/allapot.html` token → the file view opens the page (`/api/fleet/files/content?path=docs/html/allapot.html`) → the desktop hand-over returns `ok` → the desktop browser's history gains the visit (12:56:33). Screenshots at each step; the hover underline renders in both tracking states. [REQ: the-reference-is-reachable-while-the-agent-holds-the-mouse]
