## Context

Window title matching is used in three independent code paths:

1. **`bin/wt-status` `is_editor_open()`** — bash, determines "idle (IDE)" status
   - Linux: `xdotool search --name "$wt_basename"` (substring)
   - macOS: `grep -F "$wt_basename"` on cached window data
2. **`gui/platform/macos.py` `find_window_by_title()`** — Python/AppleScript, used for double-click focus, close, and open actions
   - Uses AppleScript `name contains "title"` (substring)
3. **`gui/platform/linux.py` `find_window_by_title()`** — Python/xdotool
   - Primary path: already has boundary matching (`== title` or `startswith(title + " — ")`)
   - Fallback path: `xdotool search --name pattern` (substring)

Editor window title formats:
- **Zed**: `dirname — filename` (em-dash `\u2014`)
- **VS Code/Cursor**: `filename - dirname` (hyphen)
- **Terminal.app**: `user — shell — size`
- **iTerm2**: `session-name`
- **GNOME Terminal/kitty/etc.**: varies

The false positive occurs because worktree dirs follow the pattern `<repo>-wt-<change>`, so `<repo>` is always a prefix of `<repo>-wt-<change>`.

## Goals / Non-Goals

**Goals:**
- Eliminate false positives where repo name matches worktree window titles
- Fix all three code paths (wt-status bash, macOS Python, Linux Python fallback)
- Handle known editor title formats (Zed em-dash, VS Code hyphen)
- Keep matching robust: no regressions for legitimate matches

**Non-Goals:**
- Changing how window_id values are passed (the index-based IDs from the osascript cache are fine)
- Changing the PPID chain walk or orphan cleanup logic
- Supporting arbitrary/unknown editor title formats

## Decisions

### 1. Boundary-aware matching pattern

**Decision**: Match `title` against window names using: exact match OR followed by a known separator.

Separators: ` — ` (Zed em-dash), ` - ` (VS Code hyphen). These cover all known editor title formats.

```
MATCH:     "wt-tools"         matches "wt-tools — main.py"         ✓ (exact prefix + " — ")
MATCH:     "wt-tools"         matches "wt-tools - main.py"         ✓ (exact prefix + " - ")
MATCH:     "wt-tools"         matches "wt-tools"                   ✓ (exact)
NO MATCH:  "mediapipe-python-mirror" vs "mediapipe-python-mirror-wt-screen-locked-fk — start.sh"
           ↑ next char is "-", not a separator → rejected
```

**Alternative considered**: Regex word boundary (`\b`) — rejected because repo/worktree names contain hyphens which are word boundary characters.

**Alternative considered**: Only exact match — rejected because Zed always appends ` — filename` to titles.

### 2. Implementation per code path

**`bin/wt-status` (bash):**
- Replace `grep -F "$wt_basename"` with grep + awk/post-filter that checks the character after the match
- Helper function `match_window_title()` that checks: exact 4th field match, or 4th field starts with `"$name — "` or `"$name - "`

**`gui/platform/macos.py` (AppleScript):**
- Replace `name contains "$title"` with: `name is "$title"` OR `name starts with "$title — "` OR `name starts with "$title - "`
- This is applied in `find_window_by_title()`, `focus_window()`, and `close_window()`

**`gui/platform/linux.py` (xdotool fallback):**
- The primary WM_CLASS path already has boundary matching — no change needed
- The fallback path (no app_name): add post-filtering like the primary path

### 3. Shared matching logic in Python

**Decision**: Add a `title_matches(search: str, window_title: str) → bool` utility to `gui/platform/base.py` and use it in both macos.py and linux.py fallback.

```python
def title_matches(search: str, window_title: str) -> bool:
    """Boundary-aware window title match."""
    if window_title == search:
        return True
    if window_title.startswith(search + " \u2014 "):  # em-dash (Zed)
        return True
    if window_title.startswith(search + " - "):  # hyphen (VS Code)
        return True
    return False
```

## Risks / Trade-offs

- **[Risk] Unknown editor title formats** → Mitigation: the separators ` — ` and ` - ` cover Zed, VS Code, Cursor, Windsurf. Terminal-based editors don't typically put the directory in the title. If a new editor uses a different format, it can be added to `title_matches()`.
- **[Risk] `wt-status` bash matching diverges from Python matching** → Mitigation: both use the same logic (exact or separator-prefixed), just implemented in different languages. The bash helper and Python function check the same conditions.
