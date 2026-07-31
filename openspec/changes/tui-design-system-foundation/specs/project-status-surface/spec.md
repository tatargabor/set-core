## ADDED Requirements

### Requirement: Nesting depth never decides a row width
A value's position in the answer's structure SHALL NOT set a minimum width. A nested object,
a nested list, or a value inside a table cell SHALL be laid out within the width its container
already has, and SHALL NOT force the container wider.

Specifically, the renderer SHALL NOT apply a minimum-width class to a value on the grounds of
its nesting depth. Today `web/src/components/StatusValue.tsx:344` applies `min-w-[18rem]` when
`depth > 0`, so a two-key object inside a table cell pushes the whole table past the viewport
while the same object at top level renders comfortably.

The measurement behind this: on a real answer the offending value was the **15th longest**
string the surface carried, and the longest — roughly nine times its size — rendered fine.
Length was not the variable; nesting was.

#### Scenario: A nested object inside a cell does not widen the table
- **WHEN** a row contains a cell whose value is an object with several keys
- **THEN** the table's total width is unchanged, and the page does not scroll horizontally

#### Scenario: The same value renders at two depths
- **WHEN** the same object is rendered at top level and inside a table cell
- **THEN** each fits the width available to it, and neither imposes a minimum

### Requirement: A value too large for its cell moves, and the move is announced
When a value cannot be shown whole within its cell, the renderer SHALL move it to a row detail
expansion rather than growing the row's height to fit it. The cell SHALL then show a compact
representation and a visible affordance stating that more is available.

A row whose value was displaced SHALL be identifiable without opening it. Displacement is a
form of compacting, so the surface's governing rule applies unchanged: the reader is told, in
the place they are standing, that something was withheld.

The rule's purpose is that a prose value currently wraps into a fourteen-line tower that pushes
the neighbouring rows off the display — so the row that is hardest to read is also the one that
makes its neighbours unreadable.

#### Scenario: A prose value does not build a tower
- **WHEN** a cell's value is a paragraph of prose
- **THEN** the row's height stays comparable to its neighbours, and the full text is reachable
  from that row

#### Scenario: The displacement is visible before expanding
- **WHEN** a row holds a displaced value
- **THEN** the collapsed row carries a marker saying so, without the reader expanding it

#### Scenario: A displaced value carrying a failure is marked
- **WHEN** the displaced value is in a failing state
- **THEN** the collapsed row carries the failure marker, not merely a "more" affordance
