## Why

The Memory Browse dialog currently loads ALL memories at once via `set-memory list`. With a growing number of stored memories this becomes slow — both the data fetch (full JSON dump) and the UI rendering (one QFrame card per memory). We need pagination and a smarter default view before the memory count makes the dialog unusable.

## What Changes

- **Default view switches to Context Summary**: On dialog open, show a condensed `context_summary()` overview (grouped by type, top N per category) instead of loading all memories. This is a fixed-size, fast response regardless of memory count.
- **Paginated "All Memories" mode**: Add a "Show All" button that loads memories in pages (50 at a time) with a "Load More" button, using the new `list_memories(limit=N)` parameter from shodh-memory v0.1.75.
- **CLI gains `--limit` on list and `context` command**: `set-memory list --limit 50` and `set-memory context` to support the GUI changes.
- **Search remains unchanged**: `recall` already limits to 20 results — no changes needed there.

## Capabilities

### New Capabilities
- `memory-browse-pagination`: Paginated memory listing in GUI and `--limit` flag on `set-memory list` CLI
- `memory-context-summary`: Context summary default view in GUI and `set-memory context` CLI command

### Modified Capabilities
- `memory-type-mapping`: GUI badge rendering and type filtering now also applies to context summary cards

## Impact

- **Files**: `bin/set-memory` (new CLI commands), `gui/dialogs/memory_dialog.py` (dialog rewrite)
- **Dependencies**: Requires shodh-memory >= 0.1.70 (for `context_summary()` and `list_memories(limit=)` parameters)
- **APIs**: No external API changes. Internal CLI interface adds `set-memory list --limit N` and `set-memory context [--project P]`
