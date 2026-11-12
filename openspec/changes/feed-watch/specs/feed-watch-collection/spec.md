## IN SCOPE
- Opt-in per project through a declaration file
- Read-only collection through the user's own logged-in browser, via Claude in Chrome
- Stop conditions and the run report
- One Markdown file per item, and dedupe by item id or text hash
- A source-adapter boundary, with a Facebook group feed as the first adapter

## OUT OF SCOPE
- Posting, commenting, reacting, messaging or sending of any kind
- Scrapers, headless browsers, source APIs, and parallel or bulk extraction
- Reading messengers, notifications, profiles, or any feed that is not declared
- Unattended or cloud collection

## ADDED Requirements

### Requirement: Project opt-in by declaration
The module SHALL do nothing in a project that has no `.set/feed-watch.yaml`, and the deploy SHALL install the module's skill and plugin only into a project that opts in.

#### Scenario: Project without a declaration
- **WHEN** `set-feed-watch` runs in a project with no `.set/feed-watch.yaml`
- **THEN** it SHALL exit non-zero with a message naming the missing file
- **AND** it SHALL write no file

#### Scenario: Deploy without opt-in
- **WHEN** `set-project init` runs for a project that has not opted in to the feed-watch module
- **THEN** no feed-watch skill, plugin or config file SHALL be written into that project

### Requirement: Read-only collection
Collection SHALL only read the declared feed and the permalinks of its items, in one browser tab, at human pace, and SHALL NOT post, comment, react, message or send anything.

#### Scenario: The skill forbids writes to the source
- **WHEN** the deployed skill is read
- **THEN** it SHALL state that nothing is posted, commented, reacted to or sent
- **AND** it SHALL name only the declared feed URLs as pages it may open

### Requirement: Collection stops on a stall or challenge
Collection SHALL stop at once, without refreshing or retrying, when two consecutive scrolls bring no new item, or when a login wall, captcha, verification prompt or error page appears. It SHALL also stop at the declared per-run cap, at the declared maximum age, or at the newest item already collected.

#### Scenario: Login wall
- **WHEN** a login wall appears during a run
- **THEN** the run SHALL stop
- **AND** the report SHALL name the stop reason and the number of items collected before it

#### Scenario: Empty run with the feed visible
- **WHEN** a run collects zero items while the feed shows only loading placeholders
- **THEN** the report SHALL record a stall
- **AND** it SHALL NOT report "no new items"

### Requirement: Run report keeps the counts separate
Every run SHALL report items seen, new, skipped as duplicate, skipped by the item filter, and the stop reason, each as its own figure.

#### Scenario: Mixed run
- **WHEN** a run sees 12 items, of which 3 are duplicates and 4 are filtered out
- **THEN** the report SHALL show seen 12, new 5, duplicate 3 and filtered 4, plus the stop reason

### Requirement: One file per item with the verbatim text
Each new item SHALL be written to one Markdown file in the declared directory, with header fields, the verbatim item text between the first two lines that are exactly `---`, and space for scoring. The header labels SHALL come from the project's item template when one is declared.

#### Scenario: Verbatim body
- **WHEN** an item containing typos is collected
- **THEN** the text between the two `---` lines SHALL equal the source text exactly, typos included

### Requirement: Dedupe by item id or text hash
`set-feed-watch check-new` SHALL report an item as already collected when its permalink yields an item id that is already stored, or when the normalised text hash matches a stored item's hash. The hash SHALL be the first 12 hex digits of SHA-1 over the lower-cased, whitespace-collapsed body.

#### Scenario: Same text, different link
- **WHEN** an item whose permalink is unknown has the same normalised body as a stored item
- **THEN** `check-new` SHALL exit 3 and print the stored file's path

#### Scenario: Hash compatibility with existing items
- **WHEN** `seen` runs over item files written by the consumer's first version
- **THEN** every hash SHALL equal the one the first version computed for that file

### Requirement: Source adapter boundary
Source-specific knowledge, such as the permalink pattern, the item-id extraction and the sort-order hint, SHALL live in an adapter selected by the source's `kind`, and the rest of the module SHALL NOT depend on a specific source.

#### Scenario: Unknown source kind
- **WHEN** a declaration names a `kind` that has no adapter
- **THEN** `set-feed-watch` SHALL fail validation and name the unknown kind
