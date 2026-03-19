## Why

On Linux, `find_window_by_title()` uses `xdotool search --name` which does substring matching across ALL applications. When double-clicking a worktree row (e.g. "set-core"), it matches Chrome tabs ("tatargabor/set-core - Google Chrome") and other worktree Zed windows ("set-core-wt-o_test") in addition to the correct Zed window. The code takes the first match (lowest window ID), which is often Chrome — causing wrong-window focus and apparent window cycling instead of focusing the correct editor or opening a new one.

## What Changes

- Fix `LinuxPlatform.find_window_by_title()` to use `app_name` parameter for WM_CLASS filtering (already passed by callers, currently ignored on Linux)
- Add WM_CLASS mapping for known editors (Zed → `dev.zed.Zed`, Code → `code`, etc.)
- Implement smarter title matching: exact match or Zed's `"basename — filename"` pattern, rejecting false substring matches like `"set-core-wt-o_test"`

## Capabilities

### New Capabilities

### Modified Capabilities
- `editor-integration`: Window search on Linux now filters by application class and uses precise title matching instead of broad substring search

## Impact

- `gui/platform/linux.py`: Main changes — `find_window_by_title()` rewrite with WM_CLASS support
- `gui/platform/base.py`: May need WM_CLASS mapping or extended interface
- No breaking changes — callers already pass `app_name`, behavior just becomes correct
