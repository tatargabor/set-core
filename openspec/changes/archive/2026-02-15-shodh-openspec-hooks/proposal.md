## Why

The `shodh-memory-integration` change added memory recall/remember hooks directly into 5 OpenSpec SKILL.md files. However, `openspec update` overwrites SKILL.md files, destroying these hooks. There is no mechanism to re-inject them after an update, and no `/wt:memory` skill for agents to interact with memory directly. Users need a reliable way to install/reinstall memory hooks and a slash command for memory operations.

## What Changes

- New `set-memory-hooks` CLI command that patches memory recall/remember steps into OpenSpec SKILL.md files idempotently
- New `/wt:memory` slash command (`.claude/commands/wt/memory.md`) for agents to remember, recall, list, and check memory status
- "Install Memory Hooks" action in the GUI's Memory context menu submenu, calling `set-memory-hooks install`
- After `wt-openspec update` completes, automatically re-run `set-memory-hooks install` to restore hooks
- `set-memory-hooks check` command for FeatureWorker to detect whether hooks are installed (extends `_feature_cache` with `hooks_installed` field)

## Capabilities

### New Capabilities
- `memory-hooks-cli`: CLI tool (`bin/set-memory-hooks`) that can install, check, and remove memory hook patches from OpenSpec SKILL.md files
- `memory-skill`: `/wt:memory` slash command for agents to interact with the memory system (remember, recall, list, status)
- `memory-hooks-gui`: GUI integration — "Install Memory Hooks" menu action, auto-reinstall after openspec update, hook status on [M] button tooltip

### Modified Capabilities

## Impact

- New file: `bin/set-memory-hooks`
- New file: `.claude/commands/wt/memory.md`
- Modified: `gui/control_center/mixins/menus.py` — add "Install Memory Hooks" to Memory submenu, auto-reinstall after openspec update
- Modified: `gui/control_center/mixins/table.py` — extend [M] button tooltip with hook status
- Modified: `gui/workers/feature.py` — call `set-memory-hooks check` in poll cycle
- Modified: `install.sh` — include `set-memory-hooks` in scripts array
- Modified: `tests/gui/test_29_memory.py` — test hook install menu action
