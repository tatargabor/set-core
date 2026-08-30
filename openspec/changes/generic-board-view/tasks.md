## 1. Component

- [x] 1.1 Rename `FleetBoardStrip.tsx` to `FleetBoard.tsx` (component `FleetBoard`, same fetch, same poll) and update the Fleet page import [REQ: the-summary-strip-and-the-honesty-fields-stay]
- [x] 1.2 Parse `data.cards` defensively (array of objects or absent) and place each card by its own `lane` value; a card matching no declared band, or declaring none, goes to the unknown tray [REQ: the-board-renders-the-producers-cards-in-the-producers-bands]
- [x] 1.3 Render one column per `lanes` entry in declared order, header count taken from the entry, and keep the strip as the summary line above the columns [REQ: the-board-renders-the-producers-cards-in-the-producers-bands]
- [x] 1.4 Render the generic card face (`id`, `title`, optional `kind`, `blocked` mark, `tasksDone`/`tasksTotal` progress only when both present, `plannedRelease` chip, `note`) with no producer field name anywhere in the code [REQ: the-card-face-is-domain-free-and-renders-the-generic-fields]
- [x] 1.5 Render the unknown tray hatched and header-counted from the `unknown` scalar when present [REQ: the-unknown-tray-is-the-absence-of-a-band]
- [x] 1.6 Bound the board area (max height, internal scroll per column) and keep every interaction a reading one [REQ: the-board-is-read-only]
- [x] 1.7 The board as a dockable panel kind (`board`) with the same window chrome as the other project panels — four dock edges, maximise, close — opened from a glyph in the project header; while the panel is open the inline copy stays the summary strip only [REQ: the-board-is-read-only]
- [x] 1.8 Count the project tiles (file view, work cycle, board) in the grid-tile count so the column control cannot disagree with what is drawn [REQ: the-board-is-read-only]

## 2. Tests

- [x] 2.1 Unit tests: card placement by own lane; mismatch between header count and rendered cards renders both unreconciled; out-of-array lane lands in the tray [REQ: the-board-renders-the-producers-cards-in-the-producers-bands]
- [x] 2.2 Unit tests: card face fields (progress hidden when either task field absent, never "0 of 0"; blocked mark; plannedRelease chip; note rendered; unknown extra fields ignored) [REQ: the-card-face-is-domain-free-and-renders-the-generic-fields]
- [x] 2.3 Unit tests: tray header count from the scalar, hatched tray distinct from bands [REQ: the-unknown-tray-is-the-absence-of-a-band]
- [x] 2.4 Unit tests: gap answer renders the gap and no columns; all-zero board renders words not empty columns [REQ: the-summary-strip-and-the-honesty-fields-stay]

## 3. Verification

- [x] 3.1 `tsc -b` clean; full web unit suite set-diffed against HEAD (known entries: B-129, B-130) [REQ: the-summary-strip-and-the-honesty-fields-stay]
- [x] 3.2 Look at the board in the running dashboard against the live answer; screenshot; say what is seen [REQ: the-board-renders-the-producers-cards-in-the-producers-bands]
- [x] 3.3 Answer the producer on the channel with the generic field set and the `note` mapping [REQ: the-card-face-is-domain-free-and-renders-the-generic-fields]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN the lanes array says a band holds 3 cards but 4 cards carry that band's name THEN the header shows 3, all 4 cards render, nothing reconciles or hides the difference [REQ: the-board-renders-the-producers-cards-in-the-producers-bands, scenario: the-counts-and-the-cards-disagree]
- [x] AC-2: WHEN a card's lane matches no declared entry THEN it renders in the unknown tray and no new column is invented [REQ: the-board-renders-the-producers-cards-in-the-producers-bands, scenario: a-card-names-a-band-outside-the-declared-array]
- [x] AC-3: WHEN cards carry a domain-named reason field THEN the framework renders nothing for it until the project maps it to note, and the framework's code contains no reference to the domain name [REQ: the-card-face-is-domain-free-and-renders-the-generic-fields, scenario: the-first-implementers-field-names]
- [x] AC-4: WHEN tasksDone or tasksTotal is absent THEN no progress hint renders, never "0 of 0" [REQ: the-card-face-is-domain-free-and-renders-the-generic-fields, scenario: a-card-without-progress-fields]
- [x] AC-5: WHEN the board renders with populated bands and an unknown scalar THEN the tray is distinguishable by more than position and the strip's unknown figure equals the tray header's [REQ: the-unknown-tray-is-the-absence-of-a-band, scenario: the-tray-does-not-absorb-the-bands]
- [x] AC-6: WHEN the board command returns a gap result THEN the gap renders and no card columns claim an empty board [REQ: the-summary-strip-and-the-honesty-fields-stay, scenario: the-answer-fails-after-the-board-shipped]
- [x] AC-7: WHEN the reader clicks a card THEN nothing is written and any effect is a reading effect [REQ: the-board-is-read-only, scenario: a-card-click]
- [x] AC-8: WHEN the board renders as a panel THEN it carries the same window chrome as the other project panels — dock edges, maximise, close [REQ: the-board-is-read-only]
