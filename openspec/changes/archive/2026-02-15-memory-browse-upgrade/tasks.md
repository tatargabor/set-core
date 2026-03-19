## 1. CLI Additions

- [x] 1.1 Add `--limit N` flag to `cmd_list()` in `bin/set-memory`, passing `limit=N` to `list_memories()`
- [x] 1.2 Add `cmd_context()` in `bin/set-memory` that calls `context_summary()` and outputs JSON
- [x] 1.3 Update `usage()` help text to document new `context` command and `--limit` flag

## 2. Browse Dialog Rewrite

- [x] 2.1 Add context summary view: new `_load_summary()` method calling `set-memory context`, render grouped sections with type-colored headers
- [x] 2.2 Add view toggle: "Show All" button in summary mode, "Summary" button in list mode
- [x] 2.3 Implement paginated list mode: cache full list from `set-memory list`, render 50 cards at a time with "Load More" button
- [x] 2.4 Wire search to override both views: recall results shown as cards, "Clear" returns to previous mode (summary or list)

## 3. Tests

- [x] 3.1 Add GUI test for MemoryBrowseDialog summary/list toggle and pagination in `tests/gui/`

## 4. Documentation

- [x] 4.1 Update `docs/` memory documentation with new CLI commands
- [x] 4.2 Update `docs/readme-guide.md` CLI section with `context` and `list --limit`
- [x] 4.3 Update `README.md` with new memory CLI commands
