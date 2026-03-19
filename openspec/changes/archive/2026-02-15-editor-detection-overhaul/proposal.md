## Why

The current editor detection and window focus system is IDE-centric (Zed/VSCode/Cursor/Windsurf only) and uses fragile window-title matching that breaks when editors change their title (e.g., "main.py — set-core" doesn't match `^set-core$`). Additionally, the `wt-work` auto-launch uses ~160 lines of brittle keystroke injection (xdotool key, sleep/retry loops) that often fails. Users who run Claude Code in standalone terminals (kitty, alacritty, gnome-terminal, iTerm2) have no support at all. The `--dangerously-skip-permissions` flag is hardcoded everywhere with no user choice.

## What Changes

- **BREAKING**: Replace window-title-based editor detection with PPID chain walking — start from the claude agent PID, walk up the process tree, find which window owns the process chain. This works for ANY editor or terminal without needing to know window classes or title formats.
- **BREAKING**: Remove keystroke injection auto-launch from `wt-work`. Replace with: (a) editor CLI open (`zed <path>`, `code <path>`, etc.), (b) informational tip showing the shortcut, (c) optional direct terminal launch for terminal-based setups.
- Add terminal emulators as supported editors: kitty, alacritty, wezterm, gnome-terminal, konsole, iTerm2, Terminal.app
- Add Claude permission mode config (`auto-accept` / `plan` / `allowedTools`) — user chooses during install, can change in Settings UI. Replaces hardcoded `--dangerously-skip-permissions`.
- Add `window_id` field to wt-status JSON output so GUI focus can use it directly.
- Fix `wt-work` Zed `-n` flag on Linux (forces new window instead of reusing existing).
- Add editor selection to install script and Settings dialog.
- Add `wt-loop --permission-mode` flag to override the config default (defaults to config value).

## Capabilities

### New Capabilities
- `ppid-chain-detection`: Agent-to-window discovery via process parent chain walking. Replaces class/title-based detection for editor_open, orphan detection, and window focus.
- `claude-permission-config`: Configurable Claude Code permission mode (auto-accept, plan, allowedTools) stored in config.json, selectable during install, changeable in Settings UI.

### Modified Capabilities
- `editor-integration`: Add terminal emulators as editor types, remove keystroke injection auto-launch, use editor CLI for open/focus, fix Zed -n flag.
- `orphan-agent-cleanup`: Use PPID chain instead of window-title matching for editor_open detection. Agent whose parent chain reaches a live window process = not orphan.
- `control-center`: Add editor selection to Settings dialog, consume window_id from wt-status for focus.
- `ralph-loop`: Read claude permission mode from config, add --permission-mode flag override.

## Impact

- **bin/wt-status**: New PPID chain detection replaces `is_editor_open()`, adds `window_id` to JSON output
- **bin/wt-work**: Major simplification — remove keystroke injection (~150 lines), fix Zed -n, add terminal launch, use permission config
- **bin/wt-loop**: Read permission mode from config, add --permission-mode flag
- **bin/wt-new**: Task/keybinding generation uses permission config
- **bin/wt-common.sh**: Extend SUPPORTED_EDITORS with terminal emulators
- **gui/platform/linux.py**: Add `find_window_by_pid()` method
- **gui/platform/macos.py**: Add `find_window_by_pid()` method
- **gui/control_center/mixins/handlers.py**: `on_focus()` uses window_id from status data
- **gui/dialogs/settings.py**: Add editor selection + permission mode
- **install.sh**: Add editor choice + permission mode steps, update Zed/VSCode task generation
- **config.json schema**: New `claude.permission_mode` field, extended `editor.name` values
- **tests/**: New unit tests for PPID chain, integration test scripts for Linux/macOS
