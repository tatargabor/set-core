## Decisions

- **D1 — A board, not a popover.** The panel becomes a fixed overlay under the header,
  `min(96rem, 96vw)` wide and at most 85 % of the viewport high, scrolling inside. It still
  floats above the layout and moves nothing (ui-quality: an overlay never pushes), closes on
  its own control, Escape and an outside click.
- **D2 — The text comes from the existing detail route.** The relay record holds no question
  text by design; the board reads `/api/fleet/question-relay/{id}/detail` per waiting call on
  the same 5 s cadence as the panel. No new route.
- **D3 — One click answers a single-question call.** That is the channel's own model (a tap on
  a reaction answers); the click posts to `…/answer`, the operator's own answer, so no
  exclusion or window applies — the same act the existing `answer…` overlay performs in three
  steps. A several-question call needs a pick per question and an explicit send.
- **D4 — Readable over compact here.** `text-sm`, the question with its line breaks, the
  verdict's reason in full; a long question scrolls inside its cell (max 16 rem), so one row
  cannot push the others off the screen.
