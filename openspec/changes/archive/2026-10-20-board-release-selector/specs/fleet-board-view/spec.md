## IN SCOPE

- The release selector: when it renders, its default, and what choosing does.
- Membership-driven card filtering and the draft's off-board group.
- Filter-explained emptiness and the unchanged producer headers.

## OUT OF SCOPE

- Resolving release membership in set-core — the answer names it; the surface takes it.
- Any change to the transport, the card vocabulary, or the read-only guarantee.

## ADDED Requirements

### Requirement: The release selector defaults to the producer's open draft
When the board answer carries `releasePlanned` entries with a readable release name, the
board SHALL render a release selector. Its default selection SHALL be the FIRST such
entry — the producer's own open draft — and "all cards" SHALL remain selectable. An
answer without `releasePlanned` SHALL render no selector and every card.

#### Scenario: The board opens on the draft
- **WHEN** the answer carries one draft naming two planned items
- **THEN** the selector shows that draft selected, and the columns show only the cards
  that draft's membership names — the rest of the project's cards stay hidden until
  "all cards" is chosen

#### Scenario: No drafts published
- **WHEN** the answer carries no `releasePlanned`
- **THEN** no selector renders, and every card shows exactly as before

### Requirement: Filtering follows the producer's membership, never an inference
A selected draft SHALL filter the card columns to the cards its membership names as
on-board (by card id). Column placement stays by each card's own lane. Under a selected
draft the lane header counts SHALL come from the draft's OWN membership — how many
items it places in each lane — because the whole-board figure beside a filtered column
reads as a bug (user-reported, 2026-08-30); the whole-board figures SHALL render in the
"all cards" view and in the strip legend. The surface MUST NOT count CARDS to produce a
header. The draft's planned items with no card SHALL render as their
own group, each with its stated reason, and each following the same `openTarget` click
rule as a card.

#### Scenario: An item planned but not on the board
- **WHEN** the chosen draft names an item with `onBoard: false` and a reason
- **THEN** the item renders in the draft's off-board group with its reason visible, and
  if it declares an `openTarget` the artefact is one click away — it is never invented
  into a lane column

#### Scenario: Emptiness the filter explains
- **WHEN** a lane shows no cards because the chosen draft's membership names none there
- **THEN** the column renders no mismatch claim for that emptiness — a filter is neither
  a zero nor a counts-vs-cards disagreement
