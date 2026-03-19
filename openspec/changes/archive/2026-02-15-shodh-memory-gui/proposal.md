## Why

The `set-memory` CLI and shodh-memory Python library are installed but not connected to the workflow or visible in the GUI. Memory storage is currently a single global directory, mixing memories from all projects. The 5 core OpenSpec SKILL.md files lack memory hooks — so remember/recall never fires automatically. The Control Center has no way to see memory status or browse memories.

## What Changes

- `set-memory` CLI gains **per-project storage**: auto-detects project from git root, stores memories under `~/.local/share/set-core/memory/<project-name>/`
- **Project header [M] button** in Control Center showing memory availability and count
- **Project header context menu** (new — currently right-click on header does nothing) with Memory submenu: status, browse, remember note
- **OpenSpec SKILL.md hooks**: 5 core skills gain automatic recall/remember steps (the missing piece from the original change)
- OpenSpec skill integration warning in GUI when SKILL.md files lack memory hooks

## Capabilities

### New Capabilities
- `memory-gui`: Project-level memory indicator button in header, browse dialog, remember dialog, and project header context menu with Memory submenu
- `per-project-memory`: Per-project storage isolation in `set-memory` CLI via git root auto-detection

### Modified Capabilities
- `memory-cli`: Update storage path logic from single global directory to per-project directories

## Impact

- **Files modified**: `bin/set-memory` (storage path logic), 5 SKILL.md files (memory hooks), `gui/control_center/mixins/table.py` (header widget), `gui/control_center/mixins/menus.py` (project header context menu)
- **Files added**: `gui/dialogs/memory_dialog.py` (browse/remember UI)
- **Dependencies**: `shodh-memory` Python package (optional, graceful degradation preserved)
- **No breaking changes**: existing global memories remain accessible; per-project storage creates new directories alongside
