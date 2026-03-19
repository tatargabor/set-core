# editor-integration Specification

## Purpose
TBD - created by archiving change add-multi-editor-support. Update Purpose after archive.
## Requirements
### Requirement: Multi-Editor Support
The system SHALL support multiple code editors for opening worktrees with Claude Code integration.

#### Scenario: List supported editors
- **WHEN** user runs `wt-config editor list`
- **THEN** all supported editors are displayed with availability status
- **AND** each entry shows: name, CLI command, detected (yes/no)

#### Scenario: Detect available editors
- **WHEN** set-core starts or `wt-config editor list` is run
- **THEN** the system detects which editors are installed
- **AND** detection checks standard installation paths per platform

#### Scenario: Set preferred editor
- **WHEN** user runs `wt-config editor set vscode`
- **THEN** VS Code becomes the default editor
- **AND** preference is stored in `~/.config/set-core/config.json`

#### Scenario: Invalid editor name
- **WHEN** user runs `wt-config editor set unknown`
- **THEN** an error is shown listing valid editor names

#### Scenario: Show current editor
- **WHEN** user runs `wt-config editor show`
- **THEN** the currently configured editor name is displayed
- **AND** if not configured, shows "auto (detected: <name>)"

### Requirement: Editor-Specific Worktree Opening
The system SHALL open worktrees in the configured editor and display a Claude Code startup tip.

#### Scenario: Open worktree in Zed (Linux)
- **WHEN** Zed is the configured editor
- **AND** the platform is Linux
- **AND** user runs `wt-work <change-id>`
- **THEN** Zed opens the worktree directory
- **AND** user is informed to press Ctrl+Shift+L to start Claude Code

#### Scenario: Open worktree in Zed (macOS)
- **WHEN** Zed is the configured editor
- **AND** the platform is macOS
- **AND** user runs `wt-work <change-id>`
- **THEN** Zed opens the worktree directory
- **AND** user is informed to press Ctrl+Shift+L to start Claude Code

#### Scenario: Open worktree in VS Code
- **WHEN** VS Code is the configured editor
- **AND** user runs `wt-work <change-id>`
- **THEN** VS Code opens the worktree directory via `code <path>`
- **AND** user is informed to use Claude Code extension or run `claude` in terminal

#### Scenario: Open worktree in Cursor
- **WHEN** Cursor is the configured editor
- **AND** user runs `wt-work <change-id>`
- **THEN** Cursor opens the worktree directory via `cursor <path>`
- **AND** user is informed to use Claude Code extension or run `claude` in terminal

#### Scenario: Open worktree in Windsurf
- **WHEN** Windsurf is the configured editor
- **AND** user runs `wt-work <change-id>`
- **THEN** Windsurf opens the worktree directory via `windsurf <path>`
- **AND** user is informed to use Cascade or run `claude` in terminal

#### Scenario: Editor not installed
- **WHEN** the configured editor is not found
- **THEN** an error is shown with installation instructions
- **AND** alternative detected editors are suggested

#### Scenario: Auto-create worktree if missing
- **WHEN** user runs `wt-work <change-id>` and no worktree exists for that change
- **AND** `--no-create` flag is NOT set
- **THEN** the system SHALL create the worktree automatically before opening

#### Scenario: Main branch opening
- **WHEN** user runs `wt-work` with the main branch name as change-id
- **THEN** the system SHALL open the main repo directory instead of a worktree

### Requirement: Editor-Specific Window Focus
The system SHALL focus the editor window for a worktree by delegating to the editor's CLI.

#### Scenario: Focus editor window via CLI
- **WHEN** user runs `wt-focus <change-id>`
- **THEN** the system SHALL call the configured editor's CLI open command for the worktree path
- **AND** the editor SHALL focus the existing window if already open, or open a new one

#### Scenario: No matching window found
- **WHEN** no editor window matches the worktree folder name
- **THEN** the system SHALL open a new editor window for the worktree

### Requirement: Editor Window Close
The system SHALL close the editor window for a worktree using platform-appropriate mechanisms.

#### Scenario: Close editor window on Linux
- **WHEN** the platform is Linux
- **AND** user selects "Close Editor" from the worktree context menu
- **THEN** the system finds the editor window matching the worktree folder name using xdotool
- **AND** sends WM_DELETE_WINDOW via `xdotool windowclose` (graceful close)

#### Scenario: Close editor window on macOS
- **WHEN** the platform is macOS
- **AND** user selects "Close Editor" from the worktree context menu
- **THEN** the system finds the editor window matching the worktree folder name
- **AND** closes it via AppleScript

#### Scenario: Close from GUI uses platform abstraction
- **WHEN** user selects "Close Editor" from the worktree context menu
- **THEN** the system SHALL use the Python platform layer (`gui/platform/`) with a `close_window()` method
- **AND** the close method SHALL accept a window ID returned by `find_window_by_title()`

#### Scenario: No editor window found for close
- **WHEN** user selects "Close Editor" but no editor window matches the worktree
- **THEN** the action SHALL be a silent no-op (no error dialog)

#### Scenario: Editor prompts for unsaved changes
- **WHEN** the editor has unsaved changes in the worktree
- **AND** user selects "Close Editor"
- **THEN** the editor's native unsaved-changes dialog SHALL appear
- **AND** the system SHALL NOT force-close the window

### Requirement: Editor Detection Fallback
The system SHALL automatically detect and use an available editor when not configured.

#### Scenario: Auto-detect editor order
- **WHEN** no editor is configured
- **AND** wt-work is run
- **THEN** editors are checked in order: Zed, VS Code, Cursor, Windsurf
- **AND** the first available editor is used

#### Scenario: No editor available
- **WHEN** no supported editor is detected
- **THEN** an error is shown listing all supported editors
- **AND** installation links are provided for each

