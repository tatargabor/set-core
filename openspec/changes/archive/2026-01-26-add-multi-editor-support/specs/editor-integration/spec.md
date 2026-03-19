## ADDED Requirements

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
The system SHALL open worktrees in the configured editor with appropriate Claude Code setup.

#### Scenario: Open worktree in Zed
- **WHEN** Zed is the configured editor
- **AND** user runs `wt-work <change-id>`
- **THEN** Zed opens the worktree directory with `-n` flag
- **AND** Claude Code terminal is launched via Ctrl+Shift+L keystroke (Linux with xdotool)

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

### Requirement: Editor-Specific Window Focus
The system SHALL focus the correct editor window for a worktree.

#### Scenario: Focus Zed window
- **WHEN** Zed is the configured editor
- **AND** user runs `wt-focus <change-id>`
- **THEN** xdotool searches for windows with class "Zed"
- **AND** the window containing the worktree folder name is focused

#### Scenario: Focus VS Code window
- **WHEN** VS Code is the configured editor
- **AND** user runs `wt-focus <change-id>`
- **THEN** xdotool searches for windows with class "Code"
- **AND** the window containing the worktree folder name is focused

#### Scenario: Focus Cursor window
- **WHEN** Cursor is the configured editor
- **AND** user runs `wt-focus <change-id>`
- **THEN** xdotool searches for windows with class "Cursor"
- **AND** the window containing the worktree folder name is focused

#### Scenario: Focus Windsurf window
- **WHEN** Windsurf is the configured editor
- **AND** user runs `wt-focus <change-id>`
- **THEN** xdotool searches for windows with class "Windsurf"
- **AND** the window containing the worktree folder name is focused

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

