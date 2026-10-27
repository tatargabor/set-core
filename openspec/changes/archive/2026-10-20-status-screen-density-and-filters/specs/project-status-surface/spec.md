## IN SCOPE
- How much of the screen the status surface uses, and where horizontal scrolling happens
- Row density, and how a complete record is reached from a dense row
- Search, facet filters and sorting over a rendered table
- What the surface must say whenever it is not showing every row it received
- Where view state may and may not live

## OUT OF SCOPE
- Any interpretation of a project's values — no severity ordering, no status colouring
- The project declaring which of its values are problem indicators (a contract change)
- The contract, the reader, and every existing honesty requirement, which are unchanged

## ADDED Requirements

### Requirement: Filters SHALL be derived from the shape of the data, never from a field name
The surface MAY offer a filter for a column whose values are categorical — every present value
a scalar, and the distinct values few both absolutely and relative to the number of rows. The
surface SHALL NOT decide filterability from a column's name, and every count it shows for a
filter value SHALL be counted from the data.

A list of known filterable names would work on the project in front of us and fail on the next
one. It is also the cheapest thing to build, which is why the prohibition is written down: the
coupling arrives disguised as convenience.

#### Scenario: A categorical column offers a filter
- **WHEN** a table has a column whose values are scalars with few distinct values
- **THEN** the surface SHALL offer filtering on that column, with each value's row count taken
  from the data

#### Scenario: A free-text column offers none
- **WHEN** a column's values are nearly all distinct
- **THEN** no filter SHALL be offered for it, so the control cannot degrade into one chip per
  row

#### Scenario: The column name is irrelevant to the decision
- **WHEN** two columns hold identical value distributions under different names, one of them a
  name set-core knows from its own domain
- **THEN** both SHALL be treated identically

### Requirement: Hiding rows SHALL be self-reporting and reversible in one interaction
Whenever a filter or a search causes the surface to render fewer rows than the answer
contained, it SHALL state both numbers where the row count is shown, and SHALL offer a single
control that restores every row.

This extends *compacting must never hide a failure* from values to rows. The escalation is
deliberate: a filter is chosen by the reader, which is exactly when nobody checks what is
missing, and it can hide an entire failing row rather than part of one value.

#### Scenario: A filter is active
- **WHEN** any filter or search term is applied
- **THEN** the surface SHALL show how many rows are rendered and how many were received, and a
  control that clears all filters at once

#### Scenario: No filter is active
- **WHEN** nothing is filtered
- **THEN** the surface SHALL make no claim about hidden rows, because there are none to claim

#### Scenario: A filter selects nothing
- **WHEN** a filter combination matches no row
- **THEN** the surface SHALL say so explicitly and keep the clearing control reachable, and
  SHALL NOT render an empty table that reads as an empty answer

### Requirement: Sorting SHALL be undoable back to the project's delivered order
Where the surface offers sorting, the delivered order SHALL be reachable again without
reloading, and the surface SHALL indicate when the rows are not in the project's order.

Delivery order is a decision made by the side that owns the data — the same reasoning that made
a declared section list ordered rather than ranked by a number. A sort that cannot be undone
replaces that decision silently.

#### Scenario: Sorting cycles back to the delivered order
- **WHEN** a reader sorts a column repeatedly
- **THEN** the cycle SHALL return to the order the project delivered

#### Scenario: A sorted table says it is sorted
- **WHEN** rows are not in the delivered order
- **THEN** the surface SHALL indicate it, so the order on screen is never mistaken for the
  project's own

#### Scenario: Absent values do not migrate to the top
- **WHEN** a sorted column has rows with no value
- **THEN** those rows SHALL sort last in both directions, so an absence never occupies the
  position a reader scans first

### Requirement: A dense row SHALL keep its complete record one interaction away
The surface MAY clip a cell to keep rows scannable. It SHALL NOT drop a column to achieve
density, and every clipped row SHALL be expandable to its complete record, rendered with the
deprecation and emphasis rules unchanged.

#### Scenario: A long value is clipped
- **WHEN** a cell's content exceeds the width available
- **THEN** it SHALL be clipped visibly and the complete value SHALL remain reachable

#### Scenario: Density never costs a column
- **WHEN** a table is rendered densely
- **THEN** every column present in the data SHALL still be present on screen

### Requirement: View state SHALL NOT be persisted anywhere that survives the tab
Filter selections, search terms, sort state and row expansion SHALL be held in memory only.
The surface SHALL NOT write them to `localStorage`, to a cookie, or to the URL.

A selected filter value is the project's data. The address bar is not a neutral place to keep
it: browsers persist history to disk and sync it, and a shareable filtered link would carry a
domain value out of the machine. The cost — a reload clears the view — is accepted, and is the
same trade this surface already makes by never caching an answer.

#### Scenario: Filtering leaves nothing behind
- **WHEN** a reader filters, searches or sorts
- **THEN** no filter value SHALL appear in browser storage or in the URL

#### Scenario: A reload starts clean
- **WHEN** the page is reloaded
- **THEN** the surface SHALL show every row again, rather than restoring a view whose state had
  to be stored somewhere

### Requirement: set-core's own status vocabulary SHALL NOT be applied to a project's values
Styling helpers that map set-core's run states to colours SHALL NOT be applied to values read
from a project's contract. Monospace, rules, sticky headers and block characters are frame and
MAY be used; a colour or an icon keyed on the content of a value is interpretation and SHALL
NOT.

This is the renderer's first rule arriving through a side door. A shared helper that colours
`failed` red would assert that set-core knows what a project's word means — and it would do it
in a file whose subject is styling, where nobody reviews vocabulary.

#### Scenario: A project value collides with a set-core status word
- **WHEN** a project's cell holds a string that set-core also uses as a run state
- **THEN** it SHALL be rendered exactly as any other string of the same shape

## MODIFIED Requirements

### Requirement: Compacting must never hide a failure
Where the surface shortens a long value **or renders fewer rows than it received**, the number
withheld SHALL always be stated and always be one interaction from complete.

#### Scenario: A list longer than the display limit
- **WHEN** a list exceeds the limit
- **THEN** the count withheld SHALL be shown and expandable, so shortening is never a
  silent truncation

#### Scenario: Rows withheld by a filter
- **WHEN** rows are withheld by a filter or a search
- **THEN** the number withheld SHALL be stated where the row count is shown, and clearing
  SHALL be one interaction
