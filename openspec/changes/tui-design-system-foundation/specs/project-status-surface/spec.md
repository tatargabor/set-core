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

Every top-level block SHALL be given the full width of the panel, and SHALL be responsible for
using it: a table flows its rows into side-by-side groups, a key grid flows its fields into
tracks, and prose keeps its measure. Blocks SHALL NOT be placed beside one another.

This requirement replaced a two-column arrangement that produced the defect it was meant to fix.
Placing a short block beside a tall one leaves the space under the shorter one empty BY
CONSTRUCTION — there is no third thing to pack into it — and the same hole was reported on three
different tabs. Giving every block the whole width removes the arrangement that can produce it.

#### Scenario: A narrow table with many rows uses the width instead of running down the page
- **WHEN** a table's natural width is small enough that two or more copies fit the panel
- **THEN** its rows flow into that many side-by-side groups, each carrying its own header

#### Scenario: Flowing is never a truncation
- **WHEN** a table's rows are split into groups
- **THEN** the rows on screen add up to the count the table states from its own data

#### Scenario: A table that already fills the panel is left alone
- **WHEN** a table is as wide as, or wider than, the panel
- **THEN** it renders as one table, because splitting it would make every group scroll sideways

#### Scenario: A table that fits ONCE spends the leftover width on the column that wants it
- **WHEN** a table renders as a single group and its natural width is narrower than the panel
- **THEN** the width left over widens the cell clip, so the longest column shows more of its value
  rather than the panel showing empty space beside a clipped sentence

This is the case the requirement above did not reach: a table too wide to flow into two groups and
too narrow to fill the panel used a FIXED clip and left the remainder empty. Measured on a two-row
table in a 1150px panel — the table drew at ~940px, and the cell carrying an open human decision
clipped at 42 characters with ~470px of panel unused beside it. The clip widens, not the table:
`table-layout: auto` gives spare width to the column that asks for it, so the short columns stay
short. Stretching the table itself would spread every column and rebuild the strip-of-nothing this
requirement exists to remove.

#### Scenario: One long field does not dictate the layout of its neighbours
- **WHEN** a record holds several short fields and one long one
- **THEN** the short fields flow into tracks and the long one takes a full row on its own

#### Scenario: The project's field order survives the flow
- **WHEN** a short field is followed by a long one that cannot share its row
- **THEN** the short field keeps its declared position and the remaining track is left empty,
  rather than a later field being pulled forward to fill it

The last scenario is the load-bearing one. A denser packing is available and is deliberately not
used: backfilling a gap reorders someone else's record, and this surface promotes nothing.

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
