## ADDED Requirements

### Requirement: The board page offers a Kanban view

The page SHALL offer two views of the same `board/state` data, **Waves** (the existing wave
ladder) and **Kanban**, with a toggle between them. The choice SHALL be remembered per viewer
in browser storage; when storage is unavailable or empty the page SHALL show Waves and the
toggle SHALL still work for the visit.

The Kanban view SHALL show four columns in this order: to do, in progress, blocked, done —
each with its item count — and one card per item in the column of the item's status. A card
SHALL show the item id and title, the item's wave as a tag whose colour is stable per wave,
and the updated time and machine when present. A note SHALL be a collapsed card body the
reader can open. Skipped items SHALL NOT form a column: they SHALL sit in a collapsed strip
below the columns whose summary carries their count.

A wave filter SHALL narrow the Kanban view to one wave, with all waves as the default. When
the filter hides a blocked item, the filter control SHALL say how many blocked items it is
hiding, so a narrowed board never reads as calmer than the job is.

The view and the filter SHALL survive a live update. The Kanban view SHALL use no storage
beyond the view preference, SHALL NOT change the payload or the seed, and SHALL NOT write.

#### Scenario: The view choice is remembered

- **WHEN** a viewer switches to Kanban and the page is opened again in the same browser
- **THEN** the page opens on Kanban

#### Scenario: No browser storage

- **WHEN** reading or writing browser storage throws or returns nothing
- **THEN** the page opens on Waves and the toggle still switches views for the visit

#### Scenario: Items land in their status column

- **WHEN** the state holds items that are to do, in progress, blocked, done and skipped
- **THEN** each of the first four appears as a card in its column with the column count
  matching, and the skipped item appears only inside the collapsed skipped strip, whose
  summary shows the count

#### Scenario: A card carries its wave and a folded note

- **WHEN** an item in wave `w2` has a note
- **THEN** its card shows a `w2` tag and the note is hidden until the reader opens it

#### Scenario: The filter does not hide a blocked item silently

- **WHEN** the filter is set to one wave and another wave holds a blocked item
- **THEN** only that wave's cards are shown and the filter control states the number of
  blocked items outside the filter

#### Scenario: A live update keeps the reader's place

- **WHEN** a new `board/state` snapshot arrives while Kanban is shown with a wave filter set
- **THEN** the page re-renders the new data in Kanban with the same filter
