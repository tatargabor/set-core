## Why

A project that publishes a `board` contract command can answer "where is the work" only as
numbers: the summary strip shipped under the fleet project header renders band counts, and
the user then asked for the board itself — the columns with the CARDS in them. The request
came with its own constraint, which is this project's founding split: the project supplies
the DATA, set-core supplies the ABSTRACTION. So this is a generic board view any project can
render into, not a screen shaped like the first project that asked.

## What Changes

- A board view under the fleet project's summary strip: one column per band in the
  producer's own declared order, the producer's cards rendered in their own bands.
- A domain-free CARD shape the abstraction renders (`id`, `title`, `kind`, `blocked`,
  `tasksDone`, `tasksTotal`, `plannedRelease`, `note`), so the producer maps its fields onto
  set-core's vocabulary rather than set-core learning theirs.
- The producer's values are TAKEN, never recomputed: band order and band counts come from
  the declared `lanes` array, the `unknown` scalar stays a hatched, visually separate tray
  (never a seventh band), and nothing re-derives membership or counts from the cards
  (precedent: agent-api-parity, where recomputed values ran 412 % against 164 % actual).
- The summary strip stays; the board renders beneath it, from the same answer.
- Honesty rules carry over unchanged: a failed command is a visible gap, an all-zero board
  reads as its zero, `plannedNotOnBoard` and `coverage.complete: false` stay on screen.

## Capabilities

### New Capabilities

- `fleet-board-view`: the fleet screen's board — the summary strip and the card columns a
  project publishes through its board contract answer, and the value-taking rules that keep
  set-core from inventing anything the project did not say.

### Modified Capabilities

<!-- none: the existing project-status-* specs govern the transport and the generic value
renderer, which are untouched; the strip shipped 2026-08-30 is folded into the new
capability's spec rather than edited into an unrelated one. -->

## Impact

- `web/src/components/FleetBoardStrip.tsx` — extended (and renamed `FleetBoard`) to render
  the card columns from the same answer it already fetches. No backend change: the
  project-status route already transports any declared command's answer.
- New unit tests for the board rules; the existing strip tests carry over.
- Consumer projects keep their contract untouched; the first implementer maps `mibol` to the
  generic `note` on its own side.
