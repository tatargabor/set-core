## 1. Component (module: web)

- [x] 1.1 Add optional `openTarget` to the board card vocabulary (`BoardCard`), read defensively: non-empty string only, anything else is absent (`FleetBoard.tsx`)
- [x] 1.2 Card face renders as a `<button type="button">` only when a usable `openTarget` AND a page-provided opener both exist; otherwise the plain div — carry `data-fleet-board-card-open` for tests
- [x] 1.3 New `onOpenTarget?: (path: string) => void` prop on `FleetBoard`, threaded to every card face; the board itself never derives a path from another field
- [x] 1.4 Update the component's contract doc comment (vocabulary list, the read-only exception and its reason)

## 2. Page wiring (module: web)

- [x] 2.1 Band/dock panel mount: `onOpenTarget={path => openFile(project.root, { path })}`
- [x] 2.2 Grid inline mount: same opener against the active project's root
- [x] 2.3 Full-screen mount: leave full screen first, then open into the page beneath

## 3. Tests (module: web)

- [x] 3.1 Read-only test amended: cards without a declared target are plain divs; no form/input/link anywhere
- [x] 3.2 A declaring card is a button; activating it calls the opener with EXACTLY the declared path and nothing else; a sibling without a target stays a div
- [x] 3.3 With no opener provided, even a declaring card renders as a plain div
- [x] 3.4 Zero-card and mismatch column markers still asserted (regression guard from the same session)

## 4. Ship

- [x] 4.1 `tsc -b` clean; board suite green; surface suite judged against the B-130 flake baseline (set-diff, isolation reruns) — NOT quoted from memory
- [x] 4.2 Served bundle rebuilt BEHIND the tsc gate (shared tree: the sibling session's in-flight source must never bake broken)
- [x] 4.3 Visual check on the running dashboard against the live answer
