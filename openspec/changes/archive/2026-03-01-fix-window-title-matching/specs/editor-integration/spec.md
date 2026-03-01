## MODIFIED Requirements

### Requirement: Editor-Specific Window Focus
The system SHALL focus the correct editor window for a worktree using platform-appropriate mechanisms and boundary-aware title matching.

#### Scenario: Focus editor window on Linux
- **WHEN** the platform is Linux
- **AND** user triggers focus for a worktree (via GUI or `wt-focus <change-id>`)
- **THEN** xdotool searches for windows with the editor's window class
- **AND** the window whose title exactly matches the worktree folder name, or starts with the folder name followed by ` — ` or ` - `, is activated
- **AND** windows whose title contains the folder name as a substring without a separator boundary SHALL NOT be matched

#### Scenario: Focus editor window on macOS
- **WHEN** the platform is macOS
- **AND** user triggers focus for a worktree (via GUI or `wt-focus <change-id>`)
- **THEN** AppleScript activates the editor application
- **AND** raises the window whose title exactly matches the worktree folder name, or starts with the folder name followed by ` — ` or ` - `
- **AND** windows whose title contains the folder name as a substring without a separator boundary SHALL NOT be matched

#### Scenario: Focus from GUI uses platform abstraction
- **WHEN** user double-clicks a running worktree in the Control Center
- **OR** user selects "Focus" from the context menu
- **THEN** the system uses the Python platform layer (`gui/platform/`) to find and focus the window
- **AND** the system SHALL NOT shell out to `wt-focus` from the GUI

#### Scenario: Focus from CLI on macOS
- **WHEN** user runs `wt-focus <change-id>` on macOS
- **THEN** the script uses `osascript` with AppleScript to find and focus the editor window
- **AND** the script SHALL NOT require `xdotool`

#### Scenario: No matching window found
- **WHEN** no editor window matches the worktree folder name with boundary-aware matching
- **THEN** the editor SHALL be opened for the worktree directory via CLI command

#### Scenario: Repo name is prefix of worktree name
- **WHEN** user double-clicks the main repo row (e.g., "mediapipe-python-mirror")
- **AND** a worktree window exists with title "mediapipe-python-mirror-wt-screen-locked-fk — start.sh"
- **THEN** that worktree window SHALL NOT be matched
- **AND** the editor SHALL be opened for the main repo directory instead

#### Scenario: Accessibility permission denied on macOS
- **WHEN** the system cannot control windows due to missing Accessibility permissions
- **THEN** the error is surfaced to the user with guidance to enable permissions

### Requirement: Editor Window Close
The system SHALL close the editor window for a worktree using platform-appropriate mechanisms and boundary-aware title matching.

#### Scenario: Close editor window on Linux
- **WHEN** the platform is Linux
- **AND** user selects "Close Editor" from the worktree context menu
- **THEN** the system finds the editor window matching the worktree folder name using boundary-aware matching
- **AND** sends WM_DELETE_WINDOW via `xdotool windowclose` (graceful close)

#### Scenario: Close editor window on macOS
- **WHEN** the platform is macOS
- **AND** user selects "Close Editor" from the worktree context menu
- **THEN** the system finds the editor window using boundary-aware matching
- **AND** closes it via AppleScript

#### Scenario: Close from GUI uses platform abstraction
- **WHEN** user selects "Close Editor" from the worktree context menu
- **THEN** the system SHALL use the Python platform layer (`gui/platform/`) with a `close_window()` method
- **AND** the close method SHALL accept a window ID returned by `find_window_by_title()`

#### Scenario: No editor window found for close
- **WHEN** user selects "Close Editor" but no editor window matches the worktree with boundary-aware matching
- **THEN** the action SHALL be a silent no-op (no error dialog)

#### Scenario: Editor prompts for unsaved changes
- **WHEN** the editor has unsaved changes in the worktree
- **AND** user selects "Close Editor"
- **THEN** the editor's native unsaved-changes dialog SHALL appear
- **AND** the system SHALL NOT force-close the window

## ADDED Requirements

### Requirement: Boundary-Aware Window Title Matching
The system SHALL use boundary-aware matching for all window title searches to prevent false positives from prefix-overlapping names.

#### Scenario: Exact title match
- **WHEN** the search term is "wt-tools"
- **AND** a window title is "wt-tools"
- **THEN** the match SHALL succeed

#### Scenario: Zed em-dash separator match
- **WHEN** the search term is "wt-tools"
- **AND** a window title is "wt-tools — main.py"
- **THEN** the match SHALL succeed (em-dash `\u2014` separator)

#### Scenario: VS Code hyphen separator match
- **WHEN** the search term is "wt-tools"
- **AND** a window title is "wt-tools - main.py"
- **THEN** the match SHALL succeed (hyphen separator with spaces)

#### Scenario: Reject prefix-only substring match
- **WHEN** the search term is "mediapipe-python-mirror"
- **AND** a window title is "mediapipe-python-mirror-wt-screen-locked-fk — start.sh"
- **THEN** the match SHALL fail (next character is `-`, not a separator)

#### Scenario: wt-status editor detection uses boundary matching
- **WHEN** `wt-status` checks if an editor window is open for a worktree
- **THEN** the window cache search SHALL use boundary-aware matching
- **AND** SHALL NOT use naive substring matching (`grep -F` or `contains`)

#### Scenario: Matching logic is consistent across platforms
- **WHEN** the same worktree name is searched on macOS and Linux
- **THEN** both platforms SHALL produce the same match/no-match result
- **AND** both SHALL recognize the same set of separator patterns
