# project-status-surface Specification

## Purpose
TBD - created by archiving change consumer-status-contract. Update Purpose after archive.

## Requirements

### Requirement: The renderer recognises no domain field name
Rendering decisions SHALL derive from a value's shape, never from what a field is called.

#### Scenario: A second project with different names
- **WHEN** a project publishes fields under entirely different names, in another language
- **THEN** the surface SHALL render them correctly with no change to the renderer

#### Scenario: The only names it may know
- **WHEN** the renderer treats a key as machinery rather than data
- **THEN** that key SHALL belong to the contract envelope, not to any project's domain

### Requirement: Unknown is not zero and is not success
A missing value SHALL render visibly as absent, and never as `0`, an empty list, or a
positive mark.

#### Scenario: A real zero beside a missing one
- **WHEN** one field holds `0` and another holds null
- **THEN** the zero SHALL render as a value and the null as an explicit unknown

#### Scenario: A false is a verdict
- **WHEN** a field holds `false`
- **THEN** it SHALL render as an answer, distinct from an unknown, because a producer may
  use null to mean that one of its own inputs could not be read

### Requirement: Nothing is promoted, and the renderer's own counts say what they count
The surface SHALL show a field where it sits, under the name the project gave it, and any
number the renderer itself contributes SHALL be unmistakably its own.

#### Scenario: Counting rows
- **WHEN** the renderer states how many entries a list holds
- **THEN** the wording SHALL count rows, and SHALL NOT be phrased so that it could be read
  as a claim about what the rows mean

### Requirement: A project may declare which of its own fields to emphasise
The surface SHALL honour an emphasis declaration attached to an object, drawing weight on
the named key without interpreting the name.

#### Scenario: A declared key that is absent
- **WHEN** an emphasis declaration names a key not present on the object
- **THEN** the surface SHALL draw nothing at all — not a placeholder and not a note

#### Scenario: The declaration is never data
- **WHEN** an object carries an emphasis declaration
- **THEN** the declaration itself SHALL NOT be rendered as a field

### Requirement: A project may rank its own top-level lists, and the ranking is the order
The surface SHALL honour a section declaration that names sibling keys in descending order
of weight, showing each section's label and severity word verbatim without interpreting
either.

#### Scenario: An unfamiliar vocabulary
- **WHEN** a project's severity words are ones set-core has never seen
- **THEN** the ranking SHALL still render correctly, because weight comes from position

#### Scenario: A list the declaration forgot
- **WHEN** a sibling list is not named by the declaration
- **THEN** it SHALL still be shown, unranked — a description SHALL NOT be able to hide the
  thing it describes

#### Scenario: The declaration's count disagrees with the data
- **WHEN** a declared count differs from the number of rows delivered
- **THEN** the surface SHALL state the disagreement, and the count it shows SHALL be the
  data's

#### Scenario: The key is not reserved
- **WHEN** a project publishes its own data under the same key name
- **THEN** the value SHALL be treated as a declaration only if it also has a declaration's
  shape and names at least one sibling key, so that data cannot silently disappear

### Requirement: A project may declare that a field is deprecated, and hidden is never silent
The surface SHALL hide fields the project declares deprecated, and SHALL state how many
were hidden, counting from the data.

#### Scenario: A declared name that is not in the answer
- **WHEN** a deprecation names a field the project no longer sends
- **THEN** nothing SHALL be announced as hidden, because the count comes from the data and
  the declaration only says what to look for

### Requirement: A project may attach actions to a row, and the surface never derives them
The surface SHALL offer a write only where the project attached one, with the arguments the
project computed, and SHALL tell the person acting that the record is their own assertion.

#### Scenario: A row with nothing left to acknowledge
- **WHEN** a project withdraws the action from a row
- **THEN** no control SHALL remain that could send a write with a missing argument

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

### Requirement: A reader can select rows, and the selection survives what narrows the table
The surface SHALL let a reader select individual rows and every row currently showing, and a
selected row SHALL remain selected while it is hidden by a search, a filter, a sort or the row
cap — the reader's set is theirs, not a by-product of the current view.

#### Scenario: A filter changes after rows are selected
- **WHEN** rows are selected and the reader then narrows the table so some of them no longer show
- **THEN** those rows SHALL remain in the selection, and SHALL still be selected when the
  narrowing is removed

#### Scenario: Select-all acts on what is showing, and says so
- **WHEN** the reader selects all rows with one control while a filter is active
- **THEN** only the rows currently showing SHALL be added, and the control SHALL name that
  limit rather than implying it selected the whole table

#### Scenario: A table with no rows
- **WHEN** a table has no rows at all
- **THEN** no selection control SHALL be offered, because a control that cannot select anything
  is indistinguishable from one that is broken

### Requirement: The selection states its own size and what it withholds
The surface SHALL state how many rows are selected and, whenever any selected row is not
currently visible, SHALL state how many are hidden — a selection whose size disagrees with what
the reader can see SHALL never be presented as if the two were the same.

#### Scenario: Selected rows hidden by a narrowing control
- **WHEN** some selected rows are hidden by a filter, a search or the row cap
- **THEN** the count of hidden-but-selected rows SHALL be shown beside the selection count

#### Scenario: Clearing the selection is always reachable
- **WHEN** any row is selected
- **THEN** a control that clears the whole selection SHALL be available without first removing
  the narrowing that hides part of it

### Requirement: A batch action is offered only where the project declares one, and its absence is stated
The surface SHALL offer an action on a selection only where the project declared an action for a
SET of rows, and SHALL NOT derive one from a row-level action. Where no such declaration exists,
the surface SHALL say so in words rather than offering nothing without explanation.

#### Scenario: A project declares no batch action
- **WHEN** rows are selected and the answer carries no batch action
- **THEN** the selection summary SHALL state that this project offers no action on a selection,
  and SHALL NOT render a disabled control whose reason for being disabled is unstated

#### Scenario: A row-level action exists but no batch action
- **WHEN** rows carry a row-level action and the answer declares no batch action
- **THEN** no batch control SHALL appear, because repeating an assertion once per row is a
  different act from asserting it about a set, and only the project knows which of its writes
  is which

#### Scenario: A declared batch action is rendered
- **WHEN** the answer declares a batch action and at least one row is selected
- **THEN** a single control SHALL be offered for the whole selection, and it SHALL state how
  many rows it would act on — including any that are currently hidden

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

### Requirement: A declared stage order governs presentation, and a value outside it stays visible and marked

Where a field carries a declared stage order, the surface SHALL present that field's values in the
declared order, SHALL draw a declared stage that holds no rows, and SHALL draw any value absent from
the declared order **visibly and distinctly**.

A value outside the order SHALL NOT be dropped, and SHALL NOT be sorted silently to the end. Sorting
it last without a mark is the failure this requirement exists to prevent: it is indistinguishable on
screen from a genuine final stage, so a mis-keyed value reads as finished work.

This undertaking is what buys the other half of the agreement — the producer keeps its "nothing
matched" bucket *outside* the declared order, so that "nothing matched" stays sayable, rather than
declaring it as a stage where it would be indistinguishable from a real one. A producer relying on
this SHALL NOT need to invent a private sentinel value.

The mark SHALL identify the value as outside the declared process, not as an error: an unmatched
value is a legitimate state of the producer's data, and may be the first sight of a stage the
declaration has not caught up with.

Rendering choice remains the framework's. Columns, a grouped list, or one ordered table column all
satisfy this requirement; nothing here promises a board.

#### Scenario: A declared stage holding nothing is drawn
- **WHEN** the order declares a stage that no row matches
- **THEN** that stage appears in its declared position, shown as holding no rows

#### Scenario: A value outside the order is visible and marked
- **WHEN** a row carries a stage value that appears nowhere in the declared order
- **THEN** the row is present on screen and is marked as outside the declared order

#### Scenario: An unmatched value is never quietly last
- **WHEN** rows carry a mix of declared values and one undeclared value
- **THEN** the undeclared value is not rendered as an unmarked final stage, and cannot be mistaken
  for the end of the process

#### Scenario: An absent declaration changes nothing
- **WHEN** no stage order is declared for a field
- **THEN** that field's values are ordered exactly as they are today, with no stage presentation
  applied
