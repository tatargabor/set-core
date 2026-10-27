## Why

The board renders every card the project publishes — 180 on the first real project — and
the reader's actual question ("what is planned for the open draft?") has no answer on
screen. The producer's answer now carries its own release membership
(`releasePlanned[]`), so the board can offer a selector without set-core ever resolving
membership itself.

## What Changes

- The board strip gains a release selector when the answer carries `releasePlanned`.
  Its default is the producer's FIRST OPEN DRAFT, not "all cards"; "all cards" remains
  one choice away.
- Selecting a draft filters the card columns to the cards THAT DRAFT'S MEMBERSHIP NAMES
  (`onBoard: true` items, by card id) — placement stays by each card's own lane, and the
  lane headers keep the producer's whole-board counts.
- The draft's planned items that carry no card render as their own group with each
  item's reason and, when declared, its artefact one click away (same `openTarget`
  rule as cards).
- Emptiness a filter explains is not claimed as a zero: the mismatch marker is
  suppressed for lanes whose cards are hidden by the chosen draft.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `fleet-board-view`: adds the release selector requirements (default draft, membership-
  driven filtering, the off-board group) and amends the honesty surface for filter-
  explained emptiness.

## Impact

- `web/src/components/FleetBoard.tsx` only — the page wiring is unchanged (the selector
  is inside the strip). The producer's field shape is read defensively; a missing
  `releasePlanned` renders the board exactly as before.
