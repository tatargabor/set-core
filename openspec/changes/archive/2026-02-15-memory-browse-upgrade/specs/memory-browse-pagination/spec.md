## ADDED Requirements

### Requirement: Dialogs MUST NOT load unbounded data at open time
Any GUI dialog that displays dynamic, growable data (memories, messages, logs, search results) SHALL protect against unbounded loading. At least one of the following strategies MUST be used:
- **Summary default**: open with a fixed-size overview, not the full list
- **Pagination**: render at most N items initially, offer "Load More" for the rest
- **Search-first**: start empty, load on user query only
- **Cache + render-on-demand**: fetch data once, render widgets in batches

This applies to all current and future dialogs. The rationale: widget rendering is O(n) — 2000 QFrame cards can freeze the UI for seconds. Data fetch size alone is not the bottleneck; widget creation is.

### Requirement: CLI list command supports --limit flag
`set-memory list` SHALL accept an optional `--limit N` flag that passes `limit=N` to `list_memories()`. When omitted, all memories are returned (current behavior).

#### Scenario: List with limit
- **WHEN** user runs `set-memory list --limit 50`
- **THEN** output is a JSON array of at most 50 memories
- **AND** memories are sorted by creation time (most recent first)

#### Scenario: List without limit (backward compatible)
- **WHEN** user runs `set-memory list`
- **THEN** output is a JSON array of all memories (existing behavior unchanged)

### Requirement: Browse dialog renders memories in pages of 50
The MemoryBrowseDialog SHALL render memory cards in batches of 50. A "Load More" control SHALL appear when more memories exist beyond the current batch.

#### Scenario: Initial list load
- **WHEN** user switches to list mode with 120 total memories
- **THEN** the first 50 memory cards are rendered
- **AND** a "Load More (showing 50 of 120)" button appears below the cards

#### Scenario: Load more
- **WHEN** user clicks "Load More" with 120 total memories and 50 currently shown
- **THEN** the next 50 cards are appended (100 total now shown)
- **AND** the button updates to "Load More (showing 100 of 120)"

#### Scenario: All loaded
- **WHEN** all memories have been rendered
- **THEN** the "Load More" button disappears

### Requirement: Browse dialog caches memory data
The dialog SHALL fetch memory data once and cache it in the dialog instance. "Load More" SHALL render from cache without a new subprocess call.

#### Scenario: No redundant subprocess calls
- **WHEN** user clicks "Load More" three times
- **THEN** `set-memory list` is called exactly once (at initial list load)
- **AND** subsequent batches render from the cached data
