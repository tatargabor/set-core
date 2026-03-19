## Context

The GUI's `on_focus()` method shells out to `bin/wt-focus`, a bash script that relies entirely on `xdotool` (Linux/X11). On macOS, `xdotool` doesn't exist, so focus silently fails.

A Python platform abstraction layer exists at `gui/platform/` with `macos.py` containing AppleScript-based `focus_window()` and `find_window_by_title()`. However:
1. `on_focus()` doesn't use the platform layer — it calls the bash script directly
2. `macos.py:find_window_by_title()` has a broken AppleScript that searches process names instead of window titles
3. `macos.py:focus_window()` takes a PID and sets the process frontmost, but doesn't activate a specific window

Zed window titles contain the worktree directory name (e.g., `"set-core-wt-teszt2"`).

## Goals / Non-Goals

**Goals:**
- Make editor window focus work on macOS from the GUI (double-click / Focus action)
- Make `wt-focus` CLI command work on macOS
- Fix `macos.py` platform methods so they actually work
- Keep Linux behavior unchanged

**Non-Goals:**
- Windows support (no immediate need)
- Supporting editors other than Zed on macOS (can be extended later)
- Changing the `find_window_by_title` / `focus_window` API signatures on the base class

## Decisions

### 1. GUI `on_focus()`: use platform layer directly

**Decision**: Replace the `subprocess.run(["wt-focus", ...])` call with direct Python platform calls.

**Rationale**: The platform layer already abstracts Linux vs macOS. Shelling out to a bash script that itself needs platform logic is redundant. The Python code can resolve the worktree path and call `platform.find_window_by_title()` + `platform.focus_window()` directly.

**Alternative considered**: Make `wt-focus` macOS-aware and keep the subprocess call. Rejected because it adds shell+AppleScript complexity when the Python layer already exists.

### 2. macOS `find_window_by_title()`: target editor app directly

**Decision**: Instead of scanning all processes, target the known editor application (e.g., "Zed") and search its windows by title.

```applescript
tell application "System Events"
    tell process "Zed"
        set windowList to every window whose name contains "<search>"
        if (count of windowList) > 0 then
            return name of first item of windowList
        end if
    end tell
end tell
```

**Rationale**: Searching all processes is slow and fragile. Since we know which editor to target (from config or auto-detect), we can be specific. Return the window title (not PID) so we can match it for focus.

### 3. macOS `focus_window()`: activate by app name + window title

**Decision**: Change `focus_window()` to accept a window identifier string that works on each platform. On macOS, use the editor app name and raise the specific window:

```applescript
tell application "Zed"
    activate
end tell
tell application "System Events"
    tell process "Zed"
        perform action "AXRaise" of (first window whose name contains "<title>")
    end tell
end tell
```

The `window_id` parameter semantics differ per platform (Linux: X11 window ID; macOS: window title substring). This is fine — the callers always get the ID from `find_window_by_title()` on the same platform.

### 4. `wt-focus` bash script: add macOS branch

**Decision**: Add a macOS code path using `osascript` when `xdotool` is not available. The script already detects the editor name; on macOS, use AppleScript to search Zed windows and activate the matching one.

**Rationale**: The CLI should also work on macOS for users who prefer the command line.

### 5. Pass editor name through platform methods

**Decision**: Add an optional `app_name` parameter to `find_window_by_title()` and `focus_window()` on macOS, defaulting to "Zed". The `on_focus()` handler resolves the editor name from config and passes it through.

On Linux, the `app_name` parameter is ignored (xdotool uses X11 window class from the existing flow).

## Risks / Trade-offs

- **AppleScript requires Accessibility permissions** → User may need to grant permission in System Settings > Privacy & Security > Accessibility. This is standard for window management tools; we'll surface a clear error message if it fails.
- **Window title matching is heuristic** → If a user renames their Zed window or has multiple worktrees with similar names, the wrong window could be focused. Mitigation: match on the full worktree directory basename, which is unique.
- **`focus_window` parameter semantics differ per platform** → Callers must always pair `find_window_by_title` + `focus_window` from the same platform. This is already the pattern in the codebase.
