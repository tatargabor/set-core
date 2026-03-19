## MODIFIED Requirements

### Requirement: Editor-Specific Window Focus
The system SHALL focus the correct editor window for a worktree using platform-appropriate mechanisms.

#### Scenario: Focus editor window on Linux
- **WHEN** the platform is Linux
- **AND** user triggers focus for a worktree (via GUI or `wt-focus <change-id>`)
- **THEN** the system SHALL filter windows by the editor's WM_CLASS using `xdotool search --class`
- **AND** the system SHALL match window titles precisely: exact match or the editor's folder+file pattern (e.g. "basename — filename")
- **AND** the system SHALL NOT match windows from other applications (e.g. Chrome tabs containing the worktree name)
- **AND** the system SHALL NOT match other worktree windows whose names start with the same prefix (e.g. "set-core-wt-o_test" when searching for "set-core")

#### Scenario: Focus from GUI uses platform abstraction
- **WHEN** user double-clicks a running worktree in the Control Center
- **OR** user selects "Focus" from the context menu
- **THEN** the system uses the Python platform layer (`gui/platform/`) to find and focus the window
- **AND** the system SHALL NOT shell out to `wt-focus` from the GUI

#### Scenario: Focus editor window on macOS
- **WHEN** the platform is macOS
- **AND** user triggers focus for a worktree (via GUI or `wt-focus <change-id>`)
- **THEN** AppleScript activates the editor application
- **AND** raises the specific window whose title contains the worktree folder name

#### Scenario: Focus from CLI on macOS
- **WHEN** user runs `wt-focus <change-id>` on macOS
- **THEN** the script uses `osascript` with AppleScript to find and focus the editor window
- **AND** the script SHALL NOT require `xdotool`

#### Scenario: No matching window found
- **WHEN** no editor window matches the worktree folder name
- **THEN** the system SHALL open a new editor window for the worktree
- **AND** the system SHALL NOT focus unrelated windows

#### Scenario: Accessibility permission denied on macOS
- **WHEN** the system cannot control windows due to missing Accessibility permissions
- **THEN** the error is surfaced to the user with guidance to enable permissions

#### Scenario: Unknown editor WM_CLASS on Linux
- **WHEN** the configured editor's WM_CLASS is not in the known mapping
- **AND** `app_name` is provided
- **THEN** the system SHALL fall back to substring title matching (current behavior)
- **AND** the system SHALL still return the first match

#### Scenario: No app_name provided on Linux
- **WHEN** `find_window_by_title()` is called without `app_name`
- **THEN** the system SHALL use the current substring matching behavior via `xdotool search --name`
