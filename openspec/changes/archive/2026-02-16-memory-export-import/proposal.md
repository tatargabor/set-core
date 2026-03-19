## Why

Project memory (shodh-memory) is local per-machine. Developers working on the same project across multiple machines (desktop + laptop, or team sharing knowledge) have no way to transfer accumulated memories. Export/import enables portable project knowledge.

## What Changes

- Add `set-memory export` CLI command — dumps all project memories to a single JSON file
- Add `set-memory import <file>` CLI command — imports memories with UUID-based dedup (skip duplicates)
- Add `--dry-run` flag to import for previewing what would be imported
- Add Export/Import buttons to the Memory Browse Dialog in the GUI
- File format: single JSON with version header, project name, timestamp, and records array

## Capabilities

### New Capabilities
- `memory-export-import`: CLI export/import commands with JSON format, UUID-based deduplication, and dry-run preview

### Modified Capabilities
- `control-center`: Memory Browse Dialog gains Export and Import buttons with file picker integration

## Impact

- **CLI**: New `cmd_export` and `cmd_import` functions in `bin/set-memory` bash wrapper
- **GUI**: `gui/dialogs/memory_dialog.py` — new buttons and handler methods
- **Python**: Uses existing shodh-memory `list_memories()`, `get_memory()`, `remember()` APIs — no library changes needed
- **Tests**: New CLI dedup tests (isolated SHODH_STORAGE), GUI button/dialog tests in `test_29_memory.py`
- **Docs**: README and readme-guide updates for new CLI commands
