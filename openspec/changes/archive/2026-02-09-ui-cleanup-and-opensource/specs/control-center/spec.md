## MODIFIED Requirements

### Requirement: Status Command
The system SHALL provide a `wt-status` command that displays worktree and agent status.

#### Scenario: List all worktrees with status
Given multiple worktrees exist across projects
When the user runs `wt-status`
Then each worktree is shown with:
  - Project name
  - Branch name
  - Agent status (running/compacting/waiting/idle/done)
  - Last activity time

### Requirement: Configuration Management
The GUI SHALL support persistent user configuration through a settings dialog.

#### Scenario: Open settings dialog
- **GIVEN** the Control Center is running
- **WHEN** the user clicks "Settings..." from the menu (≡)
- **THEN** a settings dialog opens with configuration tabs

#### Scenario: Control Center settings tab
- **GIVEN** the settings dialog is open
- **WHEN** the user views the "Control Center" tab
- **THEN** the following settings are available:
  - Default opacity (0.0-1.0 slider)
  - Hover opacity (0.0-1.0 slider)
  - Window width (pixels)
  - Status refresh interval (milliseconds)
  - Blink interval (milliseconds)

#### Scenario: Git settings tab
- **GIVEN** the settings dialog is open
- **WHEN** the user views the "Git" tab
- **THEN** the following settings are available:
  - Branch name prefix (default: "change/")
  - Fetch timeout in seconds

#### Scenario: Notifications settings tab
- **GIVEN** the settings dialog is open
- **WHEN** the user views the "Notifications" tab
- **THEN** the following settings are available:
  - Enable notifications (checkbox)
  - Play sound (checkbox)

#### Scenario: Save configuration
- **GIVEN** the settings dialog has modified values
- **WHEN** the user clicks "OK" or "Apply"
- **THEN** settings are saved to `~/.config/set-core/gui-config.json`
- **AND** changes take effect immediately where applicable

#### Scenario: Load configuration on startup
- **GIVEN** a config file exists at `~/.config/set-core/gui-config.json`
- **WHEN** the Control Center starts
- **THEN** all settings are loaded from the config file

#### Scenario: Default values
- **GIVEN** no config file exists or a setting is missing
- **WHEN** the Control Center starts
- **THEN** default values are used for missing settings

### Requirement: Worktree List Display
The GUI SHALL display worktrees grouped by project with visual separators.

#### Scenario: Table columns
- **GIVEN** the Control Center is displaying worktrees
- **WHEN** the table is rendered
- **THEN** the columns are: Project, Branch, Status, Skill, Ctx%

#### Scenario: Project grouping
- **GIVEN** worktrees exist across multiple projects
- **WHEN** the Control Center displays the worktree list
- **THEN** worktrees are grouped by project
- **AND** project name is shown in first column for first worktree of each group

#### Scenario: Sorting within groups
- **GIVEN** multiple worktrees in a project
- **WHEN** displayed in the list
- **THEN** they are sorted alphabetically by branch name

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

#### Scenario: Worktree submenu
- **GIVEN** the context menu is open
- **WHEN** the user hovers over "Worktree"
- **THEN** a submenu appears with options: Close, Push Branch

### Requirement: Worktree Config Dialog
The GUI SHALL provide a dialog for viewing and editing worktree-specific configuration.

#### Scenario: Open worktree config
- **GIVEN** the context menu is open
- **WHEN** the user clicks "Worktree Config..."
- **THEN** a dialog opens showing the worktree's .set-core/ config files

#### Scenario: View config tabs
- **GIVEN** the worktree config dialog is open
- **WHEN** the worktree has multiple config files
- **THEN** each config file is shown in a separate tab

#### Scenario: Edit config values
- **GIVEN** the worktree config dialog is open
- **WHEN** the user modifies a config value
- **THEN** the change is saved to the corresponding .set-core/*.json file

## REMOVED Requirements

### Requirement: JIRA settings tab (from Configuration Management)
**Reason**: JIRA integration removed entirely; will be reintroduced as a plugin
**Migration**: No migration needed — JIRA settings tab simply disappears from settings dialog

### Requirement: JIRA submenu (from Row Context Menu)
**Reason**: JIRA integration removed entirely; will be reintroduced as a plugin
**Migration**: No migration needed — JIRA submenu simply disappears from context menu
