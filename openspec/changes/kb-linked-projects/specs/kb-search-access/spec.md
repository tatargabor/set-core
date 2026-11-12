## IN SCOPE
- CLI and MCP surfaces of linked-project search

## OUT OF SCOPE
- New commands; the shape of a single project's page

## ADDED Requirements

### Requirement: The search page carries linked projects

`set-kb search` SHALL print each linked project as its own block. A block that was searched names its
hits and the command that opens one (`set-kb get <path> --project <name>`). A block that was not
searched says `NOT SEARCHED` with the reason. The JSON page SHALL carry `linked`: one object per link
with `project`, `scope`, `about` and `searched`, plus either the hit page in the main page's
shape, each hit carrying `project`, or `error`. `--no-linked` SHALL search this project only and
return an empty `linked`.

#### Scenario: The text page
- **WHEN** a search in A finds a section in linked project B
- **THEN** the page shows a `linked: B` block with that path and the `set-kb get <path> --project B` hint

#### Scenario: Only this project
- **WHEN** the search runs with `--no-linked`
- **THEN** `linked` is empty and only A's hits are returned

### Requirement: A linked project's section can be fetched, and only a linked one

`set-kb get <path> --project <name>` SHALL fetch the path from the named project's index when the
name is listed in this project's `linked`, and SHALL exit non-zero, saying the name is not a linked
project, otherwise.

#### Scenario: Fetching a linked hit
- **WHEN** `get wiki/alfa/limits.md --project B` runs in A, and A links B
- **THEN** the section's text comes back

#### Scenario: A name that is not linked
- **WHEN** `get x.md --project C` runs in A, and A does not link C
- **THEN** the command exits non-zero with "not a linked project"

### Requirement: The MCP tools pass linked search through

`kb_search` SHALL accept `linked` (default true), and `false` SHALL behave as `--no-linked`.
`kb_get` SHALL accept `project`, passed as `--project`.

#### Scenario: MCP parameters
- **WHEN** an agent calls `kb_search(query)`, `kb_search(query, linked=False)` and `kb_get(path, project="B")`
- **THEN** the first carries B's block, the second an empty `linked`, and the third B's section
