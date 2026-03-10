## MODIFIED Requirements

### Requirement: Ambiguity display in HTML report
The orchestration HTML report SHALL display ambiguities with their resolution status in a table format instead of a flat list.

#### Scenario: Resolved ambiguities shown with status
- **WHEN** `ambiguities.json` contains entries with `resolution` fields
- **THEN** the HTML report renders an ambiguity table with columns: ID, Type, Description, Resolution, Note, Resolved By

#### Scenario: Color-coded resolution status
- **WHEN** ambiguity table is rendered
- **THEN** rows are color-coded: green for `fixed`, blue for `deferred`/`planner-resolved`, gray for `ignored`, red for unresolved (no `resolution` field)

#### Scenario: Unresolved ambiguities highlighted
- **WHEN** `ambiguities.json` contains entries without `resolution` fields
- **THEN** these rows appear with red background and text "UNRESOLVED"

#### Scenario: Zero ambiguities
- **WHEN** `ambiguities.json` contains zero entries
- **THEN** the ambiguity section is omitted entirely (same as current behavior)
