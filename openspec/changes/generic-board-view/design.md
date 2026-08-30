## Context

The summary strip (`FleetBoardStrip`, shipped 2026-08-30) already fetches one board answer
per project through the project-status route and renders the counts. The producer's answer
also carries `cards` — 180 of them today — and the user asked for the board itself: columns
of cards. The constraint that shapes everything: the project supplies the data, set-core the
abstraction; the first implementer is a consumer project whose field names must not leak
into framework code; and a precedent (agent-api-parity) forbids recomputing producer values
from the records that produced them.

## Goals / Non-Goals

Goals:
- Card columns under the strip, from the same single answer, in the same component fetch.
- A generic card face defined in set-core's vocabulary.
- Values taken, never recomputed: header counts from `lanes`, tray count from `unknown`.

Non-Goals:
- No drag-and-drop, no editing, no write path of any kind.
- No new panel kind in the dock system — the board lives where the strip lives.
- No backend change.

## Decisions

**One component owns the answer; the board renders beneath the strip.** The strip already
fetches and polls the answer. Extending it (renamed `FleetBoard`) keeps one fetch, one poll
cadence, one gap rendering.
*Alternative considered:* a new dockable panel kind (`PANEL_BOARD`) — rejected for this
change: the dock system brings layout persistence and edge-docking machinery that a summary
surface does not need, and the strip's place under the project header is exactly where the
user looked for the board.

**Cards are placed by their own `lane` value; nothing is derived.** Column headers and order
come from the `lanes` array. A card whose lane matches no declared band joins the unknown
tray. If the producer's counts and its cards disagree, both render as given — the surface
does not reconcile.
*Alternative considered:* deriving band membership by filtering cards and comparing counts —
rejected: that is the recomputation the contract forbids, and a mismatch is the producer's
truth to fix, not ours to hide.

**The card face vocabulary is: `id`, `title`, `kind`, `blocked`, `tasksDone`, `tasksTotal`,
`plannedRelease`, `note`.** All optional except `id` and `title`. The first implementer maps
its domain-named reason field to `note` on its side; until then the face renders nothing
there — the framework never spells the domain name.
*Alternative considered:* adopting the producer's field names as the vocabulary — rejected:
the next project would map onto one project's domain words, and one of them is not English.

**The unknown tray is rendered as a hatched column with a band-less header**, visually
distinct by hatch and header style, not by position alone. Its header count is the
`unknown` scalar when present.

**Zero-width bands stay visible as empty columns** — the declared order renders stations
that hold nothing, consistent with the declared-order rule shipped for the status table.

## Risks / Trade-offs

- [180 cards in the header area could crowd the fleet screen] → the board area is bounded
  (`max-h` with internal scroll); the strip stays the one-glance line.
- [A producer may emit hundreds of cards later] → rendering is plain DOM lists; no
  measurement has shown a need for virtualization. Revisit if one does.
- [The card `title` is the project's content, in the project's language] → rendered
  verbatim and never translated — the same boundary the Project Status page already holds.

## Migration Plan

None: additive frontend only. The strip's behaviour is unchanged; the board renders when
the answer carries cards. The producer maps `note` on its own side when it wants the field
shown.

## Open Questions

None — the field set was offered by the producer and the shape is theirs to map onto.
