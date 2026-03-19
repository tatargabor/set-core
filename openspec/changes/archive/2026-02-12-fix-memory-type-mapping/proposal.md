## Why

shodh-memory only supports 3 experience types: `Decision`, `Learning`, `Context`. Our codebase uses `Observation` and `Event` throughout hooks, CLAUDE.md, and GUI — these silently fall back to `Context`, losing semantic meaning. Users see incorrect type badges and the memory system's categorization is broken.

Additionally, the Developer Memory feature (set-memory + shodh-memory) has no documentation in the README or readme-guide, despite being a shipped experimental feature with CLI, GUI integration, and OpenSpec hooks.

## What Changes

- **set-memory CLI**: Add type mapping in `cmd_remember` — `Observation` → `Learning`, `Event` → `Context`, with stderr warning when mapping occurs
- **set-memory CLI help**: List valid types (`Decision`, `Learning`, `Context`) and document the mapping
- **set-memory-hooks**: Update all `--type Observation` to `--type Learning`, all `--type Event` to `--type Context` in hook templates
- **CLAUDE.md**: Update proactive memory section to use only valid types (`Decision`, `Learning`, `Context`)
- **GUI RememberNoteDialog**: Change type combobox from `[Learning, Decision, Observation, Event]` to `[Learning, Decision, Context]`
- **GUI MemoryBrowseDialog**: Remove unused `Observation`/`Event` badge colors (they never appear from shodh-memory)
- **README.md**: Add `### Developer Memory (Experimental)` feature section, add `set-memory` and `set-memory-hooks` to CLI Reference
- **docs/readme-guide.md**: Add Developer Memory to the Features mandatory section list

## Capabilities

### New Capabilities

- `memory-type-mapping`: CLI-level mapping of unsupported shodh-memory types to valid equivalents, with documentation of valid types

### Modified Capabilities

- `skill-hook-automation`: Hook templates updated to use valid memory types instead of unsupported ones

## Impact

- `bin/set-memory` — cmd_remember mapping logic + help text
- `bin/set-memory-hooks` — 3 hook template strings
- `CLAUDE.md` — proactive memory section
- `gui/dialogs/memory_dialog.py` — type combobox and badge colors
- `README.md` — new feature section + CLI reference entries
- `docs/readme-guide.md` — Features section update
- After change: `set-memory-hooks install` must be re-run to update installed hooks
