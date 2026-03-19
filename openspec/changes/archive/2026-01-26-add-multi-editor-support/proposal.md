# Change: Add Multi-Editor Support

## Why
Currently set-core is hardcoded to use Zed editor only. Users may prefer other editors that support Claude Code integration (VS Code, Cursor, Windsurf). This limits adoption and flexibility.

## What Changes
- **BREAKING**: Replace hardcoded Zed with configurable editor system
- Add editor configuration to `~/.config/set-core/config.json`
- Support 4 editors: Zed, VS Code, Cursor, Windsurf
- Each editor has specific CLI command and Claude Code launch method
- Add automatic editor detection fallback chain
- Add `wt-config editor` command for configuration
- Update GUI to show current editor and allow switching

## Supported Editors

| Editor | CLI Command | Claude Code Launch | Platform |
|--------|-------------|-------------------|----------|
| **Zed** | `zed -n <path>` | Ctrl+Shift+L (xdotool) or ACP | Linux, macOS |
| **VS Code** | `code <path>` | Extension built-in, or `claude` in terminal | All |
| **Cursor** | `cursor <path>` | VSIX extension, or `claude` in terminal | All |
| **Windsurf** | `windsurf <path>` | Built-in Cascade, or `claude` in terminal | All |

## Editor Requirements for set-core

For proper set-core integration, an editor must:
1. Open a specific folder via CLI
2. Support Claude Code terminal/extension for AI coding
3. Show worktree folder name in window title (for `wt-focus`)

## Impact
- Affected specs: `worktree-tools/spec.md` (Editor Integration requirement)
- Affected code:
  - `bin/wt-common.sh` - `find_zed()` -> `find_editor()`
  - `bin/wt-work` - Editor launch logic
  - `bin/wt-focus` - Window detection (editor-specific class names)
  - `gui/control_center/mixins/handlers.py` - Editor references
  - `install.sh`, `install.ps1` - Editor detection
- New files:
  - `bin/wt-config` - Configuration management
  - `tests/test_editor_integration.py` - Automated tests

## Migration
- Existing ZED-only setups continue to work (Zed is default)
- First run after update detects available editors and suggests configuration
