## ADDED Requirements

### Requirement: Row Context Menu
The GUI SHALL provide a hierarchical context menu when right-clicking on a worktree row.

#### Scenario: Show context menu
- **GIVEN** the Control Center is displaying worktrees
- **WHEN** the user right-clicks on a worktree row
- **THEN** a context menu appears with actions and submenus for that worktree

#### Scenario: Focus Window action
- **GIVEN** the context menu is open
- **WHEN** the user clicks "Focus Window"
- **THEN** the Zed window for that worktree is brought to foreground

#### Scenario: Open in Terminal
- **GIVEN** the context menu is open
- **WHEN** the user clicks "Open in Terminal"
- **THEN** a new terminal window opens with working directory set to the worktree path

#### Scenario: Open in File Manager
- **GIVEN** the context menu is open
- **WHEN** the user clicks "Open in File Manager"
- **THEN** the system file manager opens showing the worktree directory

#### Scenario: Copy Path
- **GIVEN** the context menu is open
- **WHEN** the user clicks "Copy Path"
- **THEN** the worktree's full path is copied to the clipboard

#### Scenario: New from this Branch
- **GIVEN** the context menu is open
- **WHEN** the user clicks "New from this Branch..."
- **THEN** the New Worktree dialog opens with project and base branch pre-filled from the selected worktree

#### Scenario: Git submenu
- **GIVEN** the context menu is open
- **WHEN** the user hovers over "Git"
- **THEN** a submenu appears with options: Merge to Master, Push, Pull, Fetch

#### Scenario: JIRA submenu
- **GIVEN** the worktree has JIRA configuration
- **WHEN** the context menu is shown
- **THEN** a JIRA submenu is available with "Open Story", "Log Work...", "Sync Worklog"

#### Scenario: Worktree submenu
- **GIVEN** the context menu is open
- **WHEN** the user hovers over "Worktree"
- **THEN** a submenu appears with options: Close, Push Branch

### Requirement: New Worktree Dialog
The GUI SHALL provide an improved dialog for creating new worktrees with project and branch selection.

#### Scenario: Open new worktree dialog
- **GIVEN** the Control Center is running
- **WHEN** the user clicks the "+ New" button
- **THEN** a dialog opens with project dropdown, change ID input, and base branch dropdown

#### Scenario: Project selection
- **GIVEN** the new worktree dialog is open
- **WHEN** the user views the project dropdown
- **THEN** all registered projects are listed
- **AND** the current/default project is pre-selected

#### Scenario: Base branch selection
- **GIVEN** the new worktree dialog is open
- **WHEN** the user views the base branch dropdown
- **THEN** available branches (master, main, existing change branches) are listed

#### Scenario: Preview update
- **GIVEN** the new worktree dialog is open
- **WHEN** the user types a change ID
- **THEN** the preview updates to show the worktree path and branch name

#### Scenario: Create worktree
- **GIVEN** valid inputs are provided
- **WHEN** the user clicks "Create"
- **THEN** wt-new is called with the selected project, change ID, and base branch

### Requirement: Worktree Config Dialog
The GUI SHALL provide a dialog for viewing and editing worktree-specific configuration.

#### Scenario: Open worktree config
- **GIVEN** the context menu is open
- **WHEN** the user clicks "Worktree Config..."
- **THEN** a dialog opens showing the worktree's .set-core/ config files

#### Scenario: View config tabs
- **GIVEN** the worktree config dialog is open
- **WHEN** the worktree has multiple config files (jira.json, confluence.json)
- **THEN** each config file is shown in a separate tab

#### Scenario: Edit config values
- **GIVEN** the worktree config dialog is open
- **WHEN** the user modifies a config value
- **THEN** the change is saved to the corresponding .set-core/*.json file

### Requirement: State Persistence
The GUI SHALL persist attention state across restarts.

#### Scenario: Save attention state
- **GIVEN** worktrees are in "needs attention" state (blinking)
- **WHEN** the GUI is closed or restarted
- **THEN** the attention state is saved to gui-state.json

#### Scenario: Restore attention state
- **GIVEN** attention state was saved from previous session
- **WHEN** the GUI starts
- **THEN** previously unacknowledged worktrees continue blinking

#### Scenario: Clear attention on click
- **GIVEN** a worktree is in "needs attention" state
- **WHEN** the user double-clicks the row
- **THEN** the attention state is cleared and saved
