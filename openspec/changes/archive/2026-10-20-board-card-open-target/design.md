## Context

The board shipped as a read-only surface (change `2026-08-30-generic-board-view`); its
spec pinned a card click to reading effects on the card itself. The first real use asked
for one more reading effect: open the artefact the card IS. The producer's measurement
of its own data — its `path` field holds source documents on tickets and is absent on
105 of 180 cards — is why the target must be a declared field, never a guess.

## Goals / Non-Goals

- Goals: one optional generic field; one honest click; zero inference; the producer maps
  its canonical field onto it on its own side (agreed on the cross-project channel,
  2026-08-30).
- Non-Goals: any URL/browser navigation, any producer field name in framework code, any
  write path, any change to the card face's visual vocabulary beyond affordance.

## Decisions

- **`openTarget` is a plain string path, not an object.** One relative path is the whole
  contract; file or directory is distinguished by the file view, not by a `kind` enum
  that would only mirror what the path already says.
- **The card becomes a `<button type="button">` only when it can act.** A card with a
  target but no page-provided opener stays a div: a control that cannot act is a promise
  the surface should not make. Keyboard activation comes free with the button element.
- **The opener is injected (`onOpenTarget` prop), not imported.** The board stays page-
  agnostic; the fleet page owns what "open" means (`openFile` into its file view). The
  full-screen mount leaves full screen first, because the file view lives in the page
  beneath the overlay.
- **Existing read-only tests stay, amended.** "No controls" becomes "no controls without
  a declared target"; the no-write guarantee is asserted by the click test (handler
  called with exactly the declared path, nothing else).

## Risks / Trade-offs

- A producer mapping the wrong field onto `openTarget` would reproduce the original
  defect on its own side — accepted, because the mapping is the producer's job and the
  framework cannot second-guess a declared value without re-deriving it.

## Migration Plan

Additive and optional: no existing card changes behaviour, the producer maps when it
ships, the surface renders identically until then.

## Open Questions

- None. If the producer's emitter needs a different name, it says so on the channel and
  this change is updated before archive.
