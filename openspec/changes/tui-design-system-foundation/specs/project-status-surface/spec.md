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

### Requirement: A panel spends its width on content, not on nothing

Top-level blocks of an answer SHALL be laid out so that a block narrower than the panel does not
reserve the panel's full width. The layout SHALL be driven by available width rather than by a
fixed column count, so the same code produces two columns on a wide display and one on a narrow
one without a breakpoint anyone maintains.

Reported twice by the user against two different tabs. Measured at 1920×1080: a seven-column
table drew at roughly 700 px with about 950 px of panel empty beside it, while the next block
waited a screenful below. Neither block was wrong; the page was spending its width on nothing.

#### Scenario: Two narrow blocks share a row
- **WHEN** an answer carries two blocks that each fit within half the panel
- **THEN** they are rendered side by side, and no band of the panel is left empty beside them

#### Scenario: A block too wide for half the panel keeps the whole row
- **WHEN** a block would not fit within half the panel
- **THEN** it is given the full width rather than being placed in a half-width slot

#### Scenario: The fit is judged by the columns actually drawn
- **WHEN** a table's rows carry a nested object that the renderer spreads into several columns
- **THEN** the fit decision counts those columns, not the single key they arrived under

The last scenario is stated because the first implementation failed it, in the direction that
loses data: a four-key nested object counted as one column, a seven-column table was placed in a
half-width slot, and its final column was clipped off the right edge where nothing announced it.

### Requirement: A table wider than its panel states what it is not showing

Where a table still exceeds the width available to it, the surface SHALL state how many of its
columns are off-screen, on the line where the row count is stated. The figure SHALL be counted
from the rendered layout and SHALL be re-counted when the table is scrolled or resized.

This is the governing compacting rule applied sideways: a scrollable box that says nothing looks
identical to a table that fits, so a screen missing a column reads as complete. An edge gradient
may mark the boundary, but the gradient is an affordance and not the statement — the surface does
not report a hidden quantity it has not counted.

#### Scenario: The count is stated where the reader is standing
- **WHEN** a table is wider than the panel that holds it
- **THEN** the row-count line also states how many columns are off to the right

#### Scenario: The claim is retired once it is no longer true
- **WHEN** the reader scrolls that table to its right-hand end
- **THEN** the statement disappears rather than remaining as a stale count

#### Scenario: A table that fits makes no such claim
- **WHEN** a table fits within its panel
- **THEN** no off-screen column count is shown, because announcing hidden content that is not
  hidden is the same defect inverted
