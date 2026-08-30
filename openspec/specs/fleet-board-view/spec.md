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
The board view SHALL offer no write path. Every interaction it offers MUST be a reading one
(tooltips, scrolling); planning changes to a card remain the project's own act, done in the
project's tools.

#### Scenario: A card click
- **WHEN** the reader clicks a card
- **THEN** nothing is written anywhere, and if the click has an effect it is a reading
  effect (showing more of the card's own text), never a state change.
