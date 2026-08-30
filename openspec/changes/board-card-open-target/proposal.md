## Why

The first real use of the board produced one request: clicking a card should open the
artefact the card IS (the ticket's own document, the change's OpenSpec folder). The
board's card vocabulary has no field for that, so there is nothing a click could
honestly follow.

## What Changes

- The generic card face gains an OPTIONAL `openTarget`: a project-root-relative path to
  the artefact the card is — a file or a directory. Declared by the producer, never
  derived by set-core from any other field.
- A card that declares `openTarget` renders as a control that opens the artefact through
  the fleet page's existing file view. This is a READING act: nothing is written, the
  board keeps its no-write-path guarantee.
- A card without `openTarget` — or when the page offers no opener — renders exactly as
  before: a plain, non-clicking face.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `fleet-board-view`: the read-only requirement is amended to name the one permitted
  click (following a producer-declared `openTarget`, a reading navigation), and the
  card-face requirement is amended to carry the new optional field and its
  never-derived rule.

## Impact

- `web/src/components/FleetBoard.tsx` — the card vocabulary, the card face renderer.
- `web/src/pages/Fleet.tsx` — passes the opener (the page's `openFile`) to the board's
  three mount sites; the full-screen overlay leaves full screen before opening.
- The producer maps its canonical artefact field onto `openTarget` on its own side
  (agreed on the cross-project channel, 2026-08-30). No producer field names enter
  framework code.
