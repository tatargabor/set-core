## ADDED Requirements

### Requirement: Nesting depth never decides a row width
A value's position in the answer's structure SHALL NOT set a minimum width. A nested object,
a nested list, or a value inside a table cell SHALL be laid out within the width its container
already has, and SHALL NOT force the container wider.

The measurement behind this: on a real answer the offending value was the **15th longest**
string the surface carried, and the longest — roughly nine times its size — rendered fine.
Length was not the variable; nesting was.

**The remedy is displacement, not removing the minimum width.** An earlier draft of this
requirement named the fix as deleting the `min-w-[18rem]` that `StatusValue` applies to nested
objects. Implementing it proved that wrong, and the code being deleted said so in its own
comment: without the minimum, a nested object's value column falls to roughly one character per
line and the row gets **taller**. The minimum was a brace holding up a symptom; removing it
removes the brace, not the cause.

So the requirement is on the CELL, not on the value: a table cell SHALL NOT render a nested
structure at all. It renders a summary and the structure moves to the row detail, where the
full page width is available and the minimum width is unremarkable.

Measured on the screen this requirement exists for, before and after: the tallest row fell from
**383px to 154px** against a median that fell from 117px to 37px, with no new overflow and no
new towers on any of the other 28 screens.

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
