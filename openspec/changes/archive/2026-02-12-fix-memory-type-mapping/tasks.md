# Tasks: fix-memory-type-mapping

## 1. set-memory CLI mapping

- [x] 1.1 Add type mapping in `cmd_remember` (bin/set-memory): map `Observation` → `Learning`, `Event` → `Context`, print warning to stderr
- [x] 1.2 Update `usage()` help text to list valid types (`Decision`, `Learning`, `Context`) and note the mapping

## 2. set-memory-hooks templates

- [x] 2.1 In `bin/set-memory-hooks` `get_hook_content()`: change `--type Event` → `--type Context` in archive hook (line ~152)
- [x] 2.2 In `get_apply_remember_content()`: change `--type Observation` → `--type Learning` (error observations) and `--type Event` → `--type Context` (completion event)
- [x] 2.3 In `get_midflow_remember_content()`: change `<Decision|Observation|Learning>` → `<Decision|Learning|Context>`

## 3. CLAUDE.md

- [x] 3.1 Update proactive memory section: change `--type <Observation|Decision|Learning>` → `--type <Decision|Learning|Context>`

## 4. GUI dialogs

- [x] 4.1 In `gui/dialogs/memory_dialog.py` `RememberNoteDialog`: change type combobox items from `[Learning, Decision, Observation, Event]` to `[Learning, Decision, Context]`
- [x] 4.2 In `MemoryBrowseDialog._create_memory_card`: update `type_colors` dict — remove `Observation`/`Event`, add `Context` with amber color

## 5. README documentation

- [x] 5.1 Add `### Developer Memory (Experimental)` section under Features in README.md — describe set-memory CLI, GUI browse/remember, OpenSpec hooks integration, shodh-memory dependency. Mark as experimental.
- [x] 5.2 Add `set-memory` and `set-memory-hooks` to CLI Reference in README.md under a new "Developer Memory" category
- [x] 5.3 Update `docs/readme-guide.md` Features section (### 6) to include `**Developer Memory** — per-project remember/recall, OpenSpec hooks, GUI browse`

## 6. Tests

- [x] 6.1 Update `tests/gui/test_29_memory.py` if it references Observation/Event types — ensure it uses valid types

## 7. GUI: allow reinstalling memory hooks

- [x] 7.1 In `menus.py`: when hooks are already installed, change disabled "Memory Hooks: installed" to a clickable "Reinstall Memory Hooks..." action that calls `_run_memory_hooks_install`

## 8. Cleanup test memories

- [x] 7.1 Delete the test "test event type" memories from set-memory storage (2 orphan Context entries from our investigation)
