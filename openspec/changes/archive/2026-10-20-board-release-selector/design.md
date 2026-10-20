## Context

The user's second board request from real use: the planned-for-release view was missing,
and every card rendering at once was the reason. The producer shipped the membership
data (`releasePlanned[]`) the same day.

## Decisions

- **Filter by membership ids, not by a card's `plannedRelease` field.** The draft's own
  resolution is the producer's statement; a card field would be set-core's inference.
- **Default = first draft; the choice lives in component state.** It follows the
  producer's first draft until the reader explicitly chooses; per-process, never
  persisted — the same in-memory discipline as the answer cache.
- **Off-board items reuse the card face** (`id`, `title`, `openTarget`, `note` = reason)
  inside their own labelled group — one face vocabulary, the absence still stated.

## Risks / Trade-offs

- Whole-board lane counts beside a filtered card set can look contradictory at first
  glance; the selector's `onBoardCount/total` (the producer's own figures) sits where
  the reader chooses, and recounting the columns was the rejected alternative.

## Migration Plan

Purely additive and defensive; an answer without the new field renders identically.

## Open Questions

- None.
