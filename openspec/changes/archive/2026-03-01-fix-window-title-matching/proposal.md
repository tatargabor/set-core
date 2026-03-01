## Why

Window title matching uses naive substring search (`contains` / `grep -F`), causing false positives when worktree directory names share a common prefix with their parent repo. For example, searching for "mediapipe-python-mirror" (the main repo) incorrectly matches "mediapipe-python-mirror-wt-screen-locked-fk" (a worktree window). This causes wrong windows to be focused on double-click, false "idle (IDE)" status in wt-status, and potentially wrong windows being closed.

## What Changes

- Replace naive substring matching with boundary-aware matching across all window title search paths:
  - `wt-status` `is_editor_open()`: cache grep for editor detection
  - `gui/platform/macos.py` `find_window_by_title()`: AppleScript `contains` search
  - `gui/platform/linux.py` `find_window_by_title()`: xdotool title matching
- Title matching must account for editor-specific title formats (Zed: `dirname — filename`, VS Code: `filename - dirname`, Terminal: `user — shell`)
- Both exact match and boundary-aware partial match (separator characters like ` — `, ` - `, whitespace after the search term, NOT alphanumeric/hyphen continuation)

## Capabilities

### New Capabilities

### Modified Capabilities
- `editor-integration`: Window title matching for focus, close, and detection must use boundary-aware search instead of substring contains

## Impact

- `bin/wt-status`: `is_editor_open()` function (macOS cache grep, Linux xdotool search)
- `gui/platform/macos.py`: `find_window_by_title()`, `focus_window()`, `close_window()`
- `gui/platform/linux.py`: `find_window_by_title()` (xdotool search)
- Affects both macOS and Linux platforms
- No API or dependency changes
