## IN SCOPE
- How a structured (non-scalar) cell participates in search and filtering
- How a narrowing control is chosen for a column
- How a narrowed view is addressed and restored
- How hiding a column interacts with the surface's failure-visibility rule

## OUT OF SCOPE
- Extracting domain content from an identifier's text
- A user-facing query language
- Server-side filtering or pagination

## ADDED Requirements

### Requirement: A structured cell is searchable and filterable, or it is not offered as data
The surface SHALL include the scalar leaves of a structured cell in its free-text index, and SHALL
offer each sub-path of that cell as a column that can be narrowed on its own.

Measured before this requirement: a non-scalar cell contributed the empty string to search and was
skipped entirely for filtering. So a project that improved its data by publishing a structure would
have found the value disappear from every control — and the search box would have answered "no
rows" rather than "this is not indexed", which is the reassuring direction.

#### Scenario: A leaf inside a structured cell is reachable by search
- **WHEN** a cell holds an object or a list whose leaves include a value the reader searches for
- **THEN** the row SHALL match
- **AND** the matched leaf SHALL be visible in the rendered row rather than only inside a collapsed
  value

#### Scenario: A sub-path is narrowed like any other column
- **WHEN** a structured cell's sub-path holds values across rows
- **THEN** that sub-path SHALL be offered as a narrowable column
- **AND** the control it receives SHALL be chosen by the same rules as any other column

#### Scenario: The object itself is never searched as text
- **WHEN** a structured cell is indexed
- **THEN** its key names and punctuation SHALL NOT be part of the searchable text

Searching the serialised object matches key names, so a search for a common key would match every
row — a control that cannot narrow, which is what the facet bounds already exist to prevent.

### Requirement: A narrowing control is chosen by the shape of a column's values
The surface SHALL select a column's control from its values: categorical values SHALL keep the
existing chooser, all-numeric values SHALL receive a range, and values that ALL parse as dates
SHALL receive a period. No control SHALL be selected from a column's name.

A column of near-unique numbers technically satisfies the categorical bounds and produces a facet
of one-row chips — a control that cannot narrow anything, which this surface already treats as
worse than no control because it teaches the reader to ignore the row of controls.

#### Scenario: A numeric column with too many distinct values gets a range, not a facet
- **WHEN** a column's values are all numeric and a facet of them would not narrow usefully
- **THEN** the column SHALL receive a range control instead of a chooser

#### Scenario: One non-date value disqualifies a date column
- **WHEN** a column's values are date-shaped except for at least one that is not
- **THEN** the column SHALL NOT receive a period control
- **AND** it SHALL keep whatever control its values would otherwise earn

#### Scenario: A date embedded in an identifier is not extracted
- **WHEN** a column holds identifiers, some of which contain a date and some of which do not
- **THEN** the surface SHALL NOT derive a date from any of them
- **AND** SHALL NOT offer a period control for that column

A parser that succeeds on some rows and fails on others returns a narrowed set that is wrong in
the direction nobody checks: fewer rows, and no error.

### Requirement: A narrowed view is addressable, and what cannot be restored is reported
The surface SHALL express the active narrowing in the address, and on restoring it SHALL apply
what still matches. Any part that cannot be applied SHALL be reported beside the row count, and
SHALL NOT be silently dropped.

A stale parameter naming a column the project no longer sends would otherwise select nothing, which
on screen is indistinguishable from a project that reported no rows.

#### Scenario: A restored filter that no longer matches anything says so
- **WHEN** an address carries a narrowing whose column or value is absent from the current answer
- **THEN** the surface SHALL state what it could not apply, where it already states what a filter
  withheld
- **AND** SHALL NOT present the unfiltered set as though nothing had been asked for

### Requirement: A hidden column may not conceal a failure
Where the surface allows a column to be hidden, anything in that column that the surface would
otherwise mark SHALL be counted where the reader is standing, next to the control that hid it.

Column visibility is compaction under another name, and this surface already holds that compacting
must never hide a failure. A tidy screen reporting calm it has not verified is worse than a
cluttered one, because it is more convincing.

#### Scenario: Hiding a column that contains a marked value keeps the marking visible
- **WHEN** a reader hides a column whose values include something the surface marks
- **THEN** the count of those values SHALL remain visible beside the column control
- **AND** the reader SHALL be able to see which column they are in without unhiding every column

### Requirement: Narrowing to one column states what it withheld
Where search can be restricted to a single column, the surface SHALL keep reporting how many rows
are hidden and by which control.

Two independent narrowing controls make an empty result harder to explain, not easier, so the
existing obligation to say what was withheld applies to each of them rather than to the pair.

#### Scenario: A per-column search reports its own withholding
- **WHEN** a reader narrows the search to one column and rows are excluded
- **THEN** the row count SHALL say how many were hidden
- **AND** the control responsible SHALL be identifiable from what is shown
