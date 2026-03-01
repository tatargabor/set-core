## Why

Memory cards in the Browse dialog truncate content to 200 characters. There's no way to see the full text of a memory without using the CLI (`wt-memory get <id>`). Users need to click a card to read the complete content.

## What Changes

- Add a `MemoryDetailDialog` that shows the full content of a single memory (type, date, full content, tags, ID)
- Make memory cards clickable in `MemoryBrowseDialog` — clicking opens the detail dialog
- The detail dialog fetches full content via `wt-memory get <id>` to ensure nothing is truncated

## Capabilities

### New Capabilities
- `memory-card-detail`: Click-to-view detail dialog for memory cards in the browse dialog

### Modified Capabilities

## Impact

- `gui/dialogs/memory_dialog.py` — new `MemoryDetailDialog` class, click handler on cards
- No new dependencies, no breaking changes
