## Context

The Linux platform's `find_window_by_title()` in `gui/platform/linux.py` uses `xdotool search --name <pattern>` which does regex substring matching across ALL X11 windows. The `app_name` parameter is already passed by callers (`handlers.py` passes "Zed", "Code", etc.) but the Linux implementation ignores it entirely. This causes false matches against Chrome tabs, other worktree windows, and unrelated applications.

The macOS implementation already uses `app_name` properly via AppleScript app targeting.

## Goals / Non-Goals

**Goals:**
- Use `app_name` to filter by WM_CLASS on Linux (only search editor windows, not Chrome)
- Implement precise title matching to distinguish `set-core` from `set-core-wt-o_test`
- Keep backwards compatibility — no caller changes needed

**Non-Goals:**
- Changing macOS or Windows platform implementations
- Changing the handler/double-click logic
- Adding new config options

## Decisions

### Decision 1: Two-step filtering (WM_CLASS then title)

Instead of a single `xdotool search --name` call, use two steps:
1. `xdotool search --class <wm_class>` to get all windows of the target editor
2. Python-side title matching on the filtered list using `xdotool getwindowname`

**Why not `xdotool --class --name` combined?** Testing showed this returns empty results — xdotool's combined flag behavior is unreliable.

**Why not keep single-step?** The single `--name` search returns Chrome tabs, other editors, and unrelated apps.

### Decision 2: WM_CLASS mapping in LinuxPlatform

Add a class-level mapping from `app_name` to WM_CLASS:

```python
_WM_CLASS_MAP = {
    "Zed": "dev.zed.Zed",
    "Code": "code",
    "Cursor": "cursor",
    "Windsurf": "windsurf",
}
```

This is editor-specific knowledge that belongs in the platform layer. The mapping is determined empirically from `xprop WM_CLASS` on real windows.

### Decision 3: Title matching logic

For the title match step, check each candidate window:
- **Exact match**: `window_title == search_title` (e.g. "set-core" == "set-core")
- **Zed folder+file pattern**: `window_title.startswith(search_title + " — ")` (e.g. "set-core — CLAUDE.md")

This rejects false matches like "set-core-wt-o_test" (which starts with the search term but is a different worktree) and "tatargabor/set-core - Google Chrome" (which contains the term as a substring).

When `app_name` is not provided or unknown, fall back to current behavior (full `xdotool search --name`).

### Decision 4: Also fix `find_window_by_class()` and `close_window()` path

The same WM_CLASS mapping is useful for `find_window_by_class()`. And since `close_window()` and `focus_window()` receive window IDs (already resolved), they don't need changes.

## Risks / Trade-offs

- **Unknown WM_CLASS for new editors** → Fallback to current substring matching preserves functionality. Users can report the WM_CLASS and we add to the map.
- **Zed title format may change** → The " — " separator is Zed's current convention. If it changes, the exact match still works; only the folder+file pattern would break.
- **xdotool not installed** → Already handled (returns None, code falls through to "open new editor").
