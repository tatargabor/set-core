# fleet-board-view Specification

## Purpose
Renders a project's board answer — a summary strip plus columns of cards — as one generic,
domain-free surface in the fleet view. Created by archiving change generic-board-view.

## Requirements

### Requirement: The board renders the producer's cards in the producer's bands
The fleet screen SHALL render a project's board answer as columns of cards beneath the
summary strip: one column per entry of the producer's declared `lanes` array, in that array's
order, with each card placed under the value of its own `lane` field. The column order and
the counts in the column headers MUST come from the `lanes` array alone; set-core MUST NOT
count cards to produce a column header and MUST NOT derive column order from the cards.

#### Scenario: The counts and the cards disagree
- **WHEN** the `lanes` array says a band holds 3 cards but 4 cards carry that band's name
- **THEN** the column header shows 3, all 4 cards render in the column, and nothing on the
  surface reconciles or hides the difference — the values are the producer's.

#### Scenario: A card names a band outside the declared array
- **WHEN** a card's `lane` value matches no entry of the declared `lanes` array
- **THEN** the card renders in the unknown tray with the cards that declare no lane, and no
  new column is invented for it.

### Requirement: The card face is domain-free and renders the generic fields
The abstraction SHALL define the card as: `id` (identifier, verbatim), `title` (the work
item's own wording, verbatim), optional `kind`, optional `blocked` (truthy renders a visible
blocked mark), optional `tasksDone` and `tasksTotal` (rendered as a progress hint only when
both are present), optional `plannedRelease` (rendered as a chip), and optional `note`
(free text the producer wants on the face). set-core MUST NOT name any producer-side field
in its code; a project maps its own names onto these.

#### Scenario: The first implementer's field names
- **WHEN** a project's cards carry a domain-named reason field that corresponds to `note`
- **THEN** the framework renders nothing for it until the project maps it to `note` on its
  own side, and the framework's code contains no reference to the domain name.

#### Scenario: A card without progress fields
- **WHEN** `tasksDone` or `tasksTotal` is absent
- **THEN** the card renders without a progress hint, and never as "0 of 0".

### Requirement: The unknown tray is the absence of a band
Cards that declare no lane, or a lane outside the declared array, SHALL render in a tray
that is visually distinct from every band column — hatched, and never drawn as a seventh
column with a band's weight. The tray's header count MUST come from the answer's `unknown`
scalar when present, not from counting tray cards.

#### Scenario: The tray does not absorb the bands
- **WHEN** the board renders with both populated bands and an unknown scalar
- **THEN** the unknown tray is distinguishable from every band column by more than its
  position, and the summary strip's unknown figure equals the tray header's.

### Requirement: The summary strip and the honesty fields stay
The board view SHALL keep the summary strip above the columns, and SHALL render
`plannedNotOnBoard` entries and `coverage.complete: false` with their stated reasons where
the reader stands. A failed board command SHALL render as a visible gap with its error class
and reason, never as empty columns; an all-zero board SHALL render as the project's own zero
in words, not as six empty columns.

#### Scenario: The answer fails after the board shipped
- **WHEN** the board command returns a gap result while the board view is mounted
- **THEN** the strip shows the gap rendering and no card columns render beside it claiming
  an empty board.

### Requirement: The board is read-only
The board view SHALL offer no write path. Every interaction it offers MUST be a reading
one (tooltips, scrolling, and opening a producer-declared `openTarget` through the page's
file view); planning changes to a card remain the project's own act, done in the
project's tools.

#### Scenario: A card click
- **WHEN** the reader clicks a card
- **THEN** nothing is written anywhere, and if the click has an effect it is a reading
  effect (showing more of the card's own text, or opening the artefact the producer
  declared as the card's `openTarget`), never a state change.

### Requirement: The open target is declared by the producer, never derived
The card vocabulary SHALL carry an optional `openTarget`: a string holding the
project-root-relative path of the artefact the card IS — a file or a directory. set-core
MUST NOT derive an open target from any other card field, and MUST treat a value that is
not a non-empty string as absent. A card with no usable `openTarget` SHALL render as a
plain, non-clicking face.

#### Scenario: A card with no open target
- **WHEN** a card declares no `openTarget`, or declares one that is not a non-empty string
- **THEN** the card renders as a non-interactive face, and no control is offered for it

#### Scenario: The producer's other path-like fields are not opened
- **WHEN** a card carries producer-side fields that look like locations but no `openTarget`
- **THEN** the surface opens nothing for that card — the click would otherwise follow a
  source document rather than the artefact and look like it worked

### Requirement: Following a declared open target is a reading act
When the page provides an opener, a card that declares a usable `openTarget` SHALL render
as a control that opens that path through the page's file view. The click MUST NOT write
anything anywhere; the board's no-write-path guarantee is unchanged. When the page
provides no opener, even a card with a usable `openTarget` SHALL render as a plain face.

#### Scenario: A click on a declaring card
- **WHEN** the reader activates a card whose `openTarget` is `docs/bugs/ticket-42.md`
- **THEN** the page's file view opens that path, nothing is written anywhere, and no
  other field of the card is consulted to choose the target

#### Scenario: Full screen hands the reader back to the page
- **WHEN** the board is in full screen and the reader activates a declaring card
- **THEN** full screen is left and the file view opens in the page beneath — the artefact
  is never opened into a surface the reader cannot see

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
