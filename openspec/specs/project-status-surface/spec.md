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
Where the surface shortens a long value, the number withheld SHALL always be stated and
always be one interaction from complete.

#### Scenario: A list longer than the display limit
- **WHEN** a list exceeds the limit
- **THEN** the count withheld SHALL be shown and expandable, so shortening is never a
  silent truncation

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
