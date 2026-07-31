## ADDED Requirements

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
