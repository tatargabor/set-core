# control-center Specification

## Purpose
TBD - created by archiving change add-control-center. Update Purpose after archive.
## Requirements
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

#### Scenario: JSON output
Given worktrees exist
When the user runs `wt-status --json`
Then output is valid JSON with worktree details and summary

#### Scenario: Compact output
Given worktrees exist
When the user runs `wt-status --compact`
Then output is a single line summary suitable for status bars

#### Scenario: Per-agent skill display
- **WHEN** wt-status checks a worktree with agents
- **THEN** each agent's skill is read exclusively from `.set-core/agents/<pid>.skill`
- **AND** no fallback to `.set-core/current_skill` is used

#### Scenario: Agent with no skill file
- **WHEN** an agent PID has no corresponding `.set-core/agents/<pid>.skill` file
- **THEN** the skill field for that agent is null
- **AND** no legacy fallback file is consulted

#### Scenario: Multiple agents with different skills
- **WHEN** two agents on the same worktree have different per-PID skill files
- **THEN** each agent row shows its own skill name independently

### Requirement: Agent Detection
The system SHALL detect all Claude agent processes associated with worktrees using `ps -e` (not `pgrep`, which skips ancestors on macOS). For each detected process, the system SHALL check the parent process (PPID) to determine if the agent is orphaned.

#### Scenario: Detect running agent
Given a Claude process is running in a worktree directory
When wt-status checks that worktree
Then the agents array contains an entry with status "running" and the process PID

#### Scenario: Detect compacting agent
Given a Claude process is summarizing context (compacting)
When wt-status checks that worktree
Then the agents array contains an entry with status "compacting"

#### Scenario: Detect waiting agent
Given a Claude process is sleeping (waiting for input)
When wt-status checks that worktree
Then the agents array contains an entry with status "waiting"

#### Scenario: Detect orphan agent
Given a Claude process exists in a worktree directory
When wt-status checks that worktree
And the process's parent is not a known shell
Then the agents array contains an entry with status "orphan" and the process PID

#### Scenario: No agent
Given no Claude process exists for a worktree
When wt-status checks that worktree
Then the agents array is empty

#### Scenario: Multiple agents detected
Given two or more Claude processes have CWD in a worktree directory
When wt-status checks that worktree
Then the agents array contains one entry per process with independent status, skill, and PID

#### Scenario: CWD path-boundary matching
Given worktrees at /code/foo and /code/foo-bar
When a process has CWD /code/foo-bar
Then it matches only /code/foo-bar, not /code/foo

#### Scenario: Orphan agents excluded from output
- **WHEN** wt-status detects agents in a worktree
- **AND** those agents are "waiting" status
- **AND** no editor window is open for the worktree
- **AND** no Ralph loop is active
- **THEN** the agents are killed and excluded from the agents array

#### Scenario: Editor open status in JSON
- **WHEN** wt-status collects status for a worktree
- **THEN** the JSON entry SHALL include `"editor_open": true|false`
- **AND** the value reflects whether an editor window matching the worktree basename exists

### Requirement: Orphan Agent Detection
The system SHALL detect orphan `claude` processes — those whose parent process is not a known shell (zsh, bash, fish, sh, dash) — and classify them with status `"orphan"` in the `wt-status` JSON output.

#### Scenario: Detect orphan agent
- **WHEN** a `claude` process has CWD in a worktree directory
- **AND** its parent process (PPID) is not a shell (zsh, bash, fish, sh, dash, or their login-shell variants with `-` prefix)
- **THEN** the agent entry in the JSON output SHALL have `"status": "orphan"`

#### Scenario: Normal agent not classified as orphan
- **WHEN** a `claude` process has CWD in a worktree directory
- **AND** its parent process is a known shell (e.g., zsh, -zsh, bash, -bash)
- **THEN** the agent entry SHALL retain its normal status (running, compacting, or waiting)

#### Scenario: Orphan agent in summary counts
- **WHEN** orphan agents exist
- **THEN** they SHALL NOT be counted in the `running`, `compacting`, or `waiting` summary totals

### Requirement: Orphan Agent Display
The GUI SHALL display orphan agents with distinct visual styling to differentiate them from active agents.

#### Scenario: Orphan row background color
- **WHEN** an agent row has `"status": "orphan"`
- **THEN** the row background SHALL use the `row_orphan` color from the active color profile

#### Scenario: Orphan PID warning icon
- **WHEN** an agent row has `"status": "orphan"`
- **THEN** the PID column SHALL display `⚠ <pid>` (warning icon followed by the PID number)

#### Scenario: Orphan status icon
- **WHEN** an agent row has `"status": "orphan"`
- **THEN** the Status column SHALL display `⚠ orphan` with the `status_orphan` color

#### Scenario: Orphan color in all profiles
- **WHEN** any color profile is active (light, dark, gray, high_contrast)
- **THEN** the profile SHALL include `row_orphan`, `row_orphan_text`, and `status_orphan` color values

### Requirement: Kill Orphan Process
The GUI SHALL allow users to terminate orphan agent processes via the row context menu.

#### Scenario: Kill menu item appears for orphan rows
- **WHEN** the user right-clicks on a worktree row
- **AND** the agent for that row has `"status": "orphan"`
- **THEN** the context menu SHALL include a "⚠ Kill Orphan Process" action

#### Scenario: Kill menu item hidden for non-orphan rows
- **WHEN** the user right-clicks on a worktree row
- **AND** the agent for that row does NOT have `"status": "orphan"`
- **THEN** the context menu SHALL NOT include the "⚠ Kill Orphan Process" action

#### Scenario: Kill sends SIGTERM
- **WHEN** the user clicks "⚠ Kill Orphan Process"
- **THEN** the system SHALL send SIGTERM to the orphan process PID
- **AND** the orphan row SHALL disappear on the next status refresh

#### Scenario: Kill handles already-dead process
- **WHEN** the user clicks "⚠ Kill Orphan Process"
- **AND** the process has already exited
- **THEN** no error SHALL be shown to the user

### Requirement: Active Worktree Filter
The GUI SHALL provide a filter button that shows only actively worked-on worktrees.

#### Scenario: Toggle compact view
- **WHEN** the user clicks the filter button
- **THEN** the table shows only worktrees that have at least one non-idle agent
- **AND** ALL agents for visible worktrees are shown (not just non-idle ones)
- **AND** idle worktrees with no agents are hidden

#### Scenario: Filter re-evaluates on refresh
- **WHEN** the filter is active and the status data refreshes
- **THEN** the visible rows update to reflect current agent statuses

#### Scenario: Disable filter
- **WHEN** the user clicks the filter button while it is checked
- **THEN** all worktrees (including idle and team) are shown again

### Requirement: Interactive TUI
The system SHALL provide an interactive terminal UI for the control center.

#### Scenario: Launch TUI
Given worktrees exist
When the user runs `wt-control` (or `wt-status --interactive`)
Then an interactive TUI is displayed with worktree list

#### Scenario: Navigate and focus
Given the TUI is running
When the user selects a worktree and presses 'f'
Then that worktree's Zed window is focused

#### Scenario: Start new worktree
Given the TUI is running
When the user presses 'n'
Then prompted to create a new worktree (calls wt-new flow)

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

### Requirement: Visual Status Indicators
The GUI SHALL provide visual indicators for agent status on each row independently.

#### Scenario: Running row pulse animation
- **GIVEN** an agent row has "running" status
- **WHEN** displayed in the table
- **THEN** that specific row background pulses with green opacity animation (1s cycle)

#### Scenario: Compacting row indicator
- **GIVEN** an agent row has "compacting" status
- **WHEN** displayed in the table
- **THEN** the row has purple background with ⟳ icon

#### Scenario: Waiting row with attention blink
- **GIVEN** any agent on a worktree transitions to "waiting" and needs attention
- **WHEN** displayed in the table
- **THEN** the worktree's primary row background blinks between yellow and red

#### Scenario: Orphan row indicator
- **GIVEN** an agent row has "orphan" status
- **WHEN** displayed in the table
- **THEN** the row has gray background with ⚠ icon and muted text color

#### Scenario: Status colors by theme
- **GIVEN** the user selects a color profile (light/gray/dark/high_contrast)
- **WHEN** worktrees are displayed
- **THEN** status colors match the selected profile:
  - running: green
  - compacting: purple/magenta
  - waiting: yellow/amber
  - orphan: gray
  - idle: gray (lighter than orphan)

#### Scenario: Theme applies immediately
- **GIVEN** the user changes color profile in Settings
- **WHEN** clicking Apply or OK
- **THEN** window background and all elements update immediately

### Requirement: Ralph Loop Integration
The GUI SHALL integrate with Ralph Loop for autonomous Claude sessions.

#### Scenario: Ralph settings tab
- **GIVEN** the settings dialog is open
- **WHEN** the user views the "Ralph" tab
- **THEN** the following settings are available:
  - Terminal fullscreen (checkbox)
  - Default max iterations (spinbox)
  - Default stall threshold (spinbox, default 2, range 1-10)
  - Default iteration timeout minutes (spinbox, default 45, range 5-120)

#### Scenario: Start Loop dialog defaults
- **GIVEN** the user opens the Start Loop dialog for a worktree
- **WHEN** a `tasks.md` exists in the change directory
- **THEN** the done criteria combo SHALL default to "tasks"
- **AND** a "tasks.md found" indicator SHALL be visible

#### Scenario: Start Loop dialog manual warning
- **GIVEN** the Start Loop dialog is open
- **WHEN** the user selects "manual" done criteria
- **THEN** an inline warning SHALL appear: "Loop won't auto-stop. Use 'Stop Loop' to end."

#### Scenario: Start Loop dialog stall threshold
- **GIVEN** the Start Loop dialog is open
- **THEN** a stall threshold spinner SHALL be visible (default from settings, range 1-10)

#### Scenario: Ralph status indicator
- **GIVEN** a worktree has an active Ralph loop
- **WHEN** displayed in the table
- **THEN** an "R" button shows with color indicating status (green=running, red=stuck, orange=stalled, blue=done, gray=stopped)

#### Scenario: Ralph status tooltip details
- **GIVEN** the user hovers over the Ralph "R" button
- **THEN** the tooltip SHALL show:
  - Status (running/stuck/stalled/done/stopped)
  - Current iteration / max iterations
  - Elapsed time since loop started
  - Elapsed time of current iteration
  - Task description (first 60 chars)
  - Last commit timestamp (if any)

#### Scenario: View Ralph terminal
- **GIVEN** a Ralph loop is running
- **WHEN** user clicks "View Terminal" from context menu
- **THEN** the Ralph terminal window is focused

#### Scenario: View Ralph log
- **GIVEN** a Ralph loop has finished (terminal closed)
- **WHEN** user clicks "View Log" from context menu
- **THEN** the Ralph log file (.claude/ralph-loop.log) opens

#### Scenario: Ralph terminal logging
- **GIVEN** a Ralph loop is started
- **WHEN** the loop runs
- **THEN** all output is logged to .claude/ralph-loop.log

#### Scenario: Stop Loop records final state
- **GIVEN** a Ralph loop is running
- **WHEN** user clicks "Stop Loop" from the context menu
- **THEN** the loop-state.json SHALL be updated to "stopped"
- **AND** the current iteration SHALL have an `ended` timestamp recorded
- **AND** the terminal process SHALL be sent SIGTERM (allowing trap to fire)

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
- **WHEN** the worktree has multiple config files
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

### Requirement: Worktree List Display
The GUI SHALL display worktrees in a 6-column table: Name, PID, Status, Skill, Ctx%, Extra.

#### Scenario: Table columns
- **GIVEN** the table is displayed
- **WHEN** rendering column headers
- **THEN** the columns are: Name, PID, Status, Skill, Ctx%, Extra (6 total)
- **AND** Name merges former "Project" and "Change" columns
- **AND** PID shows the claude process ID per agent row

#### Scenario: Name column content for worktree rows
- **GIVEN** a local worktree row is rendered
- **WHEN** the Name column is populated
- **THEN** it shows the change ID / branch name (with star prefix for main repo)

#### Scenario: Name column content for team rows
- **GIVEN** a team worktree row is rendered
- **WHEN** the Name column is populated
- **THEN** it shows `member: change_id` (with lightning prefix for own machines)

#### Scenario: Extra column replaces J column
- **GIVEN** the table is displayed
- **WHEN** rendering the last column
- **THEN** the column header is "Extra" instead of "J"
- **AND** it contains Ralph indicator (R button)

#### Scenario: Project grouping
- **GIVEN** worktrees exist across multiple projects
- **WHEN** the Control Center displays the worktree list
- **THEN** worktrees are grouped by project with header rows spanning all columns
- **AND** each agent gets its own row with independent PID, Status, Skill, Ctx%

#### Scenario: Sorting within groups
- **GIVEN** multiple worktrees in a project
- **WHEN** displayed in the list
- **THEN** main repo appears first, then sorted alphabetically by change ID

#### Scenario: Multi-agent rows
- **GIVEN** a worktree has multiple agents
- **WHEN** displayed in the table
- **THEN** each agent is a separate row; primary row has Name + Extra, secondary rows have empty Name/Extra
- **AND** all agent rows map back to the parent worktree for focus/context-menu actions

#### Scenario: Per-agent Ctx%
- **GIVEN** a worktree has N agents with N session files
- **WHEN** Ctx% is calculated
- **THEN** agent[i] reads from the (i+1)th-freshest session file

#### Scenario: Worktree with no editor dimmed
- **WHEN** a worktree has `editor_open: false` in the status data
- **AND** the worktree has no active agents
- **THEN** the row text SHALL be rendered with reduced opacity or gray color

### Requirement: Multi-Agent Row Display
The GUI SHALL display separate rows for each agent when multiple agents run on the same worktree.

#### Scenario: Single agent row
- **WHEN** a worktree has exactly one agent
- **THEN** the worktree is displayed as a single row with Name, Status, Skill, Ctx%, and Extra columns populated

#### Scenario: Multiple agent rows
- **WHEN** a worktree has N agents (N > 1)
- **THEN** the worktree is displayed as N rows
- **AND** each row has its own PID, Status, Skill, and Ctx% (per-agent session file matching)
- **AND** the first row additionally has the Name (branch label) and Extra column
- **AND** subsequent rows have empty Name and Extra

#### Scenario: Agent row visual distinction
- **WHEN** a secondary agent row is rendered (not the first agent for a worktree)
- **THEN** the row has empty Name column and its own PID, making it visually subordinate but identifiable

#### Scenario: Per-agent context usage
- **WHEN** a worktree has multiple agents
- **THEN** each agent row shows its own Ctx% from the Nth-freshest session file (matching detect_agents order)

#### Scenario: Row background colors for agent rows
- **WHEN** an agent row has status "running"
- **THEN** the row background pulses green (same animation as current worktree rows)

#### Scenario: Focus action from agent row
- **WHEN** the user double-clicks or uses "Focus Window" on any agent row (primary or secondary)
- **THEN** the Zed window for the parent worktree is focused (not individual agent terminals)

### Requirement: Robust GUI Launch
The system SHALL start the Control Center GUI reliably regardless of how it is invoked.

#### Scenario: Launch via symlink
- **GIVEN** wt-control is symlinked from ~/.local/bin to the source directory
- **WHEN** the user runs `wt-control`
- **THEN** the GUI starts without import errors
- **AND** all relative imports within the gui package resolve correctly

#### Scenario: Launch directly
- **GIVEN** the user is in the set-core source directory
- **WHEN** the user runs `python gui/main.py`
- **THEN** the GUI starts without import errors

#### Scenario: Launch as module
- **GIVEN** the user is in the set-core source directory
- **WHEN** the user runs `python -m gui.main`
- **THEN** the GUI starts without import errors

#### Scenario: Launch from desktop entry
- **GIVEN** install.sh has been run
- **WHEN** the user launches "Worktree Control Center" from Alt+F2 or application menu
- **THEN** the GUI starts without import errors
- **AND** no terminal window is required

#### Scenario: Launch from macOS app bundle
- **GIVEN** install.sh has been run on macOS
- **WHEN** the user launches "WT Control" from Spotlight, Alfred, Raycast, or Dock
- **THEN** the GUI starts without import errors
- **AND** no terminal window is required
- **AND** the app bundle delegates to `~/.local/bin/wt-control`

#### Scenario: Startup failure diagnostics
- **GIVEN** the GUI fails to start (missing dependency, import error, etc.)
- **WHEN** the user runs `wt-control`
- **THEN** the error message is displayed to stderr
- **AND** the error includes the Python traceback for debugging

### Requirement: Installation Verification
The installer SHALL verify the GUI can start after installation.

#### Scenario: Verify GUI startup
- **GIVEN** install.sh has completed dependency installation
- **WHEN** the installer runs verification
- **THEN** it tests that wt-control can start
- **AND** reports success or failure to the user

### Requirement: Dialog Always-On-Top
The GUI SHALL ensure the Control Center window and all its dialogs remain visible on top of other applications on macOS by maintaining NSStatusWindowLevel (25) across all app activation state changes.

#### Scenario: CC stays above normal apps after clicking another app
- **WHEN** the Control Center is visible at NSStatusWindowLevel (25)
- **AND** the user clicks on another application (e.g., Zed editor)
- **THEN** the Control Center SHALL remain visible above the other application
- **AND** the NSWindow level SHALL be 25 (NSStatusWindowLevel)

#### Scenario: Level enforcement on app state change
- **WHEN** the application activation state changes (active → inactive or inactive → active)
- **THEN** the system SHALL verify the NSWindow level is 25
- **AND** correct it within 100ms if Qt6 has reset it

#### Scenario: Periodic level enforcement backup
- **WHEN** the Control Center is running
- **THEN** a periodic timer SHALL check the NSWindow level every 5 seconds
- **AND** restore it to 25 if it has drifted

#### Scenario: Level enforcement after show_window
- **WHEN** the Control Center is shown (e.g., from tray icon click)
- **AND** `setWindowFlags()` recreates the NSWindow
- **THEN** the native level and collection behavior SHALL be re-applied

#### Scenario: System dialog stays on top
- **WHEN** a QMessageBox, QInputDialog, or QFileDialog is opened from the Control Center
- **THEN** the dialog has `WindowStaysOnTopHint` set
- **AND** the dialog is visible above other applications

#### Scenario: Ad-hoc dialog stays on top
- **WHEN** an inline QDialog is created (e.g., Ralph Loop config, Team Worktree Details)
- **THEN** the dialog has `WindowStaysOnTopHint` set

#### Scenario: Helper wrappers for system dialogs
- **WHEN** code needs to show a QMessageBox, QInputDialog, or QFileDialog
- **THEN** wrapper functions from `gui/dialogs/helpers.py` MUST be used instead of direct Qt static methods
- **AND** the wrappers handle `WindowStaysOnTopHint` automatically

#### Scenario: Window does not hide on deactivation
- **WHEN** the user activates another application
- **THEN** the Control Center window SHALL NOT hide
- **AND** `hidesOnDeactivate` SHALL be set to False on the native NSWindow

### Requirement: Application Icon
The GUI SHALL display a custom application icon in the window decoration and taskbar.

#### Scenario: Icon loaded on startup
- **WHEN** the Control Center starts
- **THEN** the application icon SHALL be set via `QApplication.setWindowIcon()`
- **AND** the icon SHALL be loaded from `assets/icon.png` relative to the project root

#### Scenario: Graceful fallback
- **WHEN** the icon file does not exist
- **THEN** the application SHALL start without error
- **AND** the default Qt icon SHALL be used

### Requirement: Idle IDE status display

The GUI SHALL display a distinct "idle (IDE)" status with icon `◇` for worktrees where the editor is open but no Claude agent is running.

#### Scenario: Editor open, no agent
- **WHEN** a worktree has `editor_open=true` and an empty agents array
- **THEN** the status column shows `◇ idle (IDE)` with a muted blue color
- **AND** the row uses `row_idle_ide` background and `row_idle_ide_text` text color

#### Scenario: Editor closed, no agent
- **WHEN** a worktree has `editor_open=false` and an empty agents array
- **THEN** the status column shows `○ idle` with the existing idle gray color
- **AND** the row uses muted/dimmed styling (existing behavior)

#### Scenario: Editor open with agents
- **WHEN** a worktree has `editor_open=true` and agents in the array
- **THEN** the agent statuses (running/waiting/compacting/orphan) are displayed as normal
- **AND** the `idle (IDE)` status is NOT shown (agent status takes precedence)

#### Scenario: Color profile support
- **WHEN** any of the 4 color profiles is active (light, dark, gray, high_contrast)
- **THEN** `status_idle_ide`, `row_idle_ide`, and `row_idle_ide_text` colors are defined and visible

### Requirement: Editor-Specific Window Focus

Double-click on a worktree row SHALL check for an existing IDE window, regardless of agent status.

- If an IDE window exists for the worktree → focus it
- If no IDE window exists → open it via `wt-work`

The decision SHALL be based solely on window presence, not agent status.

#### Scenario: IDE window exists

- **WHEN** user double-clicks a worktree row
- **AND** an editor window matches the worktree folder name
- **THEN** that editor window SHALL be focused

#### Scenario: No IDE window exists

- **WHEN** user double-clicks a worktree row
- **AND** no editor window matches the worktree folder name
- **THEN** `wt-work` SHALL be called to open the worktree in the editor
- **AND** the GUI SHALL NOT block or freeze

#### Scenario: No IDE window with active agent

- **WHEN** user double-clicks a worktree row with an active agent (e.g. Ralph loop)
- **AND** no editor window matches the worktree folder name
- **THEN** `wt-work` SHALL be called to open the worktree in the editor
- **AND** the active agent SHALL NOT be affected

### Requirement: Row Visual Feedback
The system SHALL apply row background color across ALL columns of a worktree row, including columns that use cellWidgets (e.g., the Extra column with Ralph buttons).

#### Scenario: Running row pulse covers all columns
- **WHEN** a worktree row has a running agent and the pulse animation updates
- **THEN** the green pulse background SHALL be visible across every column, including the Extra column with cellWidgets

#### Scenario: Waiting row static color covers all columns
- **WHEN** a worktree row is in waiting state
- **THEN** the yellow/amber background SHALL be visible across every column, including the Extra column

#### Scenario: Attention blink covers all columns
- **WHEN** a worktree row needs attention and the blink timer fires
- **THEN** the blink background color SHALL toggle across every column, including the Extra column with cellWidgets

#### Scenario: Compacting row color covers all columns
- **WHEN** a worktree row is in compacting state
- **THEN** the purple background SHALL be visible across every column, including the Extra column

### Requirement: Terminal vs IDE Agent Display
The system SHALL visually distinguish agents running in the configured IDE from agents running in a plain terminal.

#### Scenario: Agent in configured IDE shows standard waiting
- **WHEN** a worktree has an agent with status "waiting"
- **AND** the `editor_type` from wt-status matches a known IDE process name (zed, code, cursor, windsurf)
- **THEN** the agent SHALL be displayed with the standard orange `⚡ waiting` icon and colors

#### Scenario: Agent in terminal shows dimmed waiting
- **WHEN** a worktree has an agent with status "waiting"
- **AND** the `editor_type` from wt-status is truthy but does NOT match a known IDE process name
- **THEN** the agent SHALL be displayed with dimmed/muted colors (reusing idle palette)
- **AND** the status text SHALL still read "waiting"

#### Scenario: Running agent always shows green regardless of editor type
- **WHEN** a worktree has an agent with status "running"
- **THEN** the agent SHALL always be displayed with the standard green running indicator
- **AND** the display SHALL NOT be affected by `editor_type`

#### Scenario: No editor_type falls back to standard display
- **WHEN** a worktree has an agent
- **AND** the `editor_type` is null or empty
- **THEN** the standard status display SHALL be used (no dimming)

### Requirement: Signal handler error boundaries
All Qt signal handler methods that process background worker results SHALL be wrapped with try/except error handling that logs the exception at ERROR level and continues execution. The UI SHALL NOT crash or freeze due to a single malformed worker result.

#### Scenario: Worker emits bad data
- **WHEN** a background worker emits a signal with unexpected or malformed data
- **THEN** the signal handler logs the exception at ERROR level to the wt-control logger
- **AND** the UI continues operating with the last known good state

#### Scenario: Table rebuild exception
- **WHEN** `refresh_table_display()` throws an exception during rendering
- **THEN** the exception is caught and logged
- **AND** the table retains its previous state rather than being left half-rendered

### Requirement: Opaque table cell backgrounds
All table cell backgrounds SHALL use fully opaque colors (alpha=255). No alpha-transparent colors SHALL be used for QTableWidgetItem backgrounds. When a transparent background is requested, it SHALL be replaced with the current theme's `bg_dialog` color.

#### Scenario: Idle row background on Linux X11
- **WHEN** an idle worktree row is rendered on a frameless window
- **THEN** the row background is the opaque `bg_dialog` color, not transparent

#### Scenario: Pulse animation on running rows
- **WHEN** a running row's pulse animation updates
- **THEN** the pulse color is pre-blended with `bg_dialog` to produce an opaque color
- **AND** no `setAlphaF()` is used on the color

### Requirement: Styled background attribute
The QMainWindow SHALL set `WA_StyledBackground` attribute to ensure the stylesheet background is always painted, preventing compositor transparency on Linux X11.

#### Scenario: Window background rendering
- **WHEN** the Control Center window is displayed on Linux X11
- **THEN** the window background is fully opaque regardless of compositor settings

### Requirement: Focus Action Editor-Type Awareness
The system SHALL optimize the focus action based on the worktree's editor type.

#### Scenario: Focus worktree with IDE editor type
- **WHEN** user triggers focus for a worktree
- **AND** the `editor_type` matches a known IDE process name
- **THEN** the system SHALL first search by window title with the configured app name
- **AND** fall back to `window_id` if title search fails

#### Scenario: Focus worktree with terminal editor type
- **WHEN** user triggers focus for a worktree
- **AND** the `editor_type` is truthy but NOT a known IDE process name
- **AND** a `window_id` is available
- **THEN** the system SHALL skip the title-based IDE search
- **AND** focus the window directly using `window_id`

#### Scenario: Focus worktree with no window
- **WHEN** user triggers focus for a worktree
- **AND** no `window_id` is available
- **AND** no title-based search finds a window
- **THEN** the system SHALL open the worktree in the configured editor

