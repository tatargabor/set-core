# team-sync Specification

## Purpose

Git-based team synchronization for the Control Center. Makes visible who's working on what, which changes they're on, and warns about conflicts.

## ADDED Requirements

### Requirement: Control Branch Initialization

The system SHALL provide a command to initialize the team sync infrastructure.

#### Scenario: Initialize wt-control branch

- **GIVEN** a project with git repository
- **WHEN** the user runs `wt-control-init`
- **THEN** an orphan branch named `wt-control` is created
- **AND** a hidden worktree `.wt-control/` is created in the project root
- **AND** directory structure `members/`, `queue/`, `chat/` is created
- **AND** `.wt-control/` is added to `.gitignore`

#### Scenario: Initialize from remote

- **GIVEN** `wt-control` branch exists on remote but not locally
- **WHEN** the user runs `wt-control-init`
- **THEN** the branch is fetched from remote
- **AND** a local worktree is created tracking the remote branch

#### Scenario: Already initialized

- **GIVEN** `.wt-control/` worktree already exists
- **WHEN** the user runs `wt-control-init`
- **THEN** an error is shown: "wt-control already initialized"
- **AND** hint: "Use --force to re-initialize"

#### Scenario: Force re-initialization

- **GIVEN** `.wt-control/` worktree exists
- **WHEN** the user runs `wt-control-init --force`
- **THEN** the existing worktree and branch are removed
- **AND** a fresh orphan branch and worktree are created

#### Scenario: Push to remote

- **GIVEN** initialization is complete
- **WHEN** the branch doesn't exist on remote
- **THEN** the branch is pushed to origin
- **OR** a warning is shown if push fails

### Requirement: Member Status Sync

The system SHALL synchronize member status via the wt-control branch.

#### Scenario: Sync local status

- **GIVEN** wt-control is initialized
- **WHEN** the user runs `wt-control-sync`
- **THEN** member status is written to `members/{name}.json`
- **AND** the JSON includes: name, display_name, hostname, status, changes, last_seen

#### Scenario: Member name format

- **GIVEN** git user.name is "John Smith" and hostname is "WorkStation"
- **WHEN** member status is generated
- **THEN** `name` is "john-smith@workstation" (sanitized, lowercase)
- **AND** `display_name` is "John Smith@WorkStation" (original case)

#### Scenario: Pull before sync

- **GIVEN** wt-control is initialized
- **WHEN** the user runs `wt-control-sync --pull`
- **THEN** `git pull --rebase` is executed first
- **AND** then local status is synced

#### Scenario: Push after sync

- **GIVEN** wt-control is initialized
- **WHEN** the user runs `wt-control-sync --push`
- **THEN** local status is synced
- **AND** `git push` is executed after

#### Scenario: Full sync mode

- **GIVEN** wt-control is initialized
- **WHEN** the user runs `wt-control-sync --full`
- **THEN** pull, sync, and push are executed in order

#### Scenario: JSON output

- **GIVEN** wt-control is initialized with member data
- **WHEN** the user runs `wt-control-sync --json`
- **THEN** output is JSON with: `my_name`, `members[]`, `conflicts[]`

#### Scenario: Commit amend for same member

- **GIVEN** last commit was from the same member
- **WHEN** `wt-control-sync` creates a new commit
- **THEN** the previous commit is amended (to reduce history noise)

### Requirement: Conflict Detection

The system SHALL detect when multiple members work on the same change.

#### Scenario: Detect change-id conflict

- **GIVEN** john has `add-feature` in changes
- **AND** peter has `add-feature` in changes
- **WHEN** `wt-control-sync --json` is called
- **THEN** `conflicts` array contains: `{change_id: "add-feature", members: ["john@...", "peter@..."]}`

#### Scenario: No conflict

- **GIVEN** john has `add-auth` and peter has `fix-bug`
- **WHEN** `wt-control-sync --json` is called
- **THEN** `conflicts` array is empty

### Requirement: GUI Team Status Display

The GUI SHALL display team member status in the main window.

#### Scenario: Team label when enabled

- **GIVEN** team sync is enabled in settings
- **WHEN** team data is received from TeamWorker
- **THEN** a team status label is shown with active/waiting members

#### Scenario: Active members display

- **GIVEN** Peter has status "active" (running agent)
- **WHEN** team label is displayed
- **THEN** Peter is shown with green ● icon

#### Scenario: Waiting members display

- **GIVEN** Anna has status "waiting"
- **WHEN** team label is displayed
- **THEN** Anna is shown with yellow ⚡ icon

#### Scenario: Conflict warning in label

- **GIVEN** a conflict exists on change "add-feature"
- **WHEN** team label is displayed
- **THEN** conflict is shown: "! add-feature"

#### Scenario: Team label hidden when disabled

- **GIVEN** team sync is disabled in settings
- **WHEN** the Control Center is displayed
- **THEN** the team label is hidden

### Requirement: GUI Team Settings

The GUI SHALL provide settings for team synchronization at two levels: global and project-specific.

#### Scenario: Global team settings tab

- **GIVEN** the general settings dialog is open
- **WHEN** the user views the "Team" tab
- **THEN** only global settings are available:
  - Sync interval (spinbox, ms) - applies to all projects

#### Scenario: Project-specific team settings dialog

- **GIVEN** the user right-clicks a project or worktree
- **WHEN** the user selects "Team Settings..." from the context menu
- **THEN** a project-specific Team Settings dialog opens with:
  - Enable team synchronization (checkbox)
  - Auto-sync in background (checkbox)
  - Initialize wt-control branch button
  - Chat key generation section

#### Scenario: Project team settings storage

- **GIVEN** team settings are modified for a project
- **WHEN** the user clicks OK
- **THEN** settings are stored in `config.team.projects[project_name]`
- **AND** each project can have independent enabled/auto_sync settings

#### Scenario: Initialize from project settings

- **GIVEN** the Project Team Settings dialog is open
- **WHEN** the user clicks "Initialize wt-control branch"
- **THEN** `wt-control-init` is executed for that project
- **AND** result is shown in status label

#### Scenario: Apply project team settings

- **GIVEN** project team settings are modified
- **WHEN** the user clicks OK
- **THEN** TeamWorker behavior updates for that project
- **AND** team icons appear in project header if enabled

### Requirement: Background Team Sync

The GUI SHALL poll team status in the background.

#### Scenario: TeamWorker polling

- **GIVEN** team sync is enabled for at least one project
- **WHEN** the Control Center is running
- **THEN** TeamWorker calls `wt-control-sync --full --json` periodically

#### Scenario: Polling interval (global)

- **GIVEN** sync_interval_ms is set to 30000 in global team settings
- **WHEN** TeamWorker is running
- **THEN** sync happens every 30 seconds for all team-enabled projects

#### Scenario: Polling disabled

- **GIVEN** team sync is disabled for ALL projects
- **WHEN** the Control Center is running
- **THEN** TeamWorker does not call wt-control-sync

#### Scenario: Error handling

- **GIVEN** wt-control-sync fails (timeout, not initialized)
- **WHEN** TeamWorker receives error
- **THEN** error is logged but not shown to user (silent failure)

### Requirement: Team Worktrees Display

The GUI SHALL display other team members' worktrees in the main table, grouped by project.

#### Scenario: Project header rows

- **GIVEN** team sync is enabled and members have active changes
- **WHEN** the worktree table is displayed
- **THEN** each project has a header row with project name, team filter button, and chat button (if unread)
- **AND** team worktrees appear directly under their project's local worktrees

#### Scenario: Team row styling

- **GIVEN** team worktrees are displayed
- **WHEN** viewing the table
- **THEN** team rows have:
  - Gray text color (blue for "my machines")
  - Italic font
  - Member name prefix (e.g., "peter:")
  - Only status icon (no PID, Ctx%, J columns)

#### Scenario: Team rows not interactive

- **GIVEN** team worktrees are displayed
- **WHEN** the user right-clicks or double-clicks a team row
- **THEN** no context menu appears
- **AND** no action is triggered

#### Scenario: Per-project team filter toggle

- **GIVEN** the Control Center is displayed with team sync enabled
- **WHEN** the user clicks a project's filter button
- **THEN** team worktrees are filtered for that project only
- **AND** cycles through: All Team → My Machines → Hide → All Team

### Requirement: Worktree Filtering

The system SHALL filter out internal worktrees from the display.

#### Scenario: Hide .wt-control worktree

- **GIVEN** a `.wt-control` worktree exists in a project
- **WHEN** `wt-status --json` is called
- **THEN** the `.wt-control` worktree is NOT included in the output

### Requirement: Hostname Change Cleanup

The system SHALL automatically cleanup old member files when hostname changes.

#### Scenario: Detect hostname change

- **GIVEN** previous hostname was "old-pc" stored in `.wt-control/.local-state/hostname`
- **AND** current hostname is "new-pc"
- **WHEN** `wt-control-sync` runs
- **THEN** old member file `members/john@old-pc.json` is deleted
- **AND** current hostname is saved to `.local-state/hostname`

#### Scenario: First sync (no previous hostname)

- **GIVEN** `.wt-control/.local-state/hostname` does not exist
- **WHEN** `wt-control-sync` runs
- **THEN** current hostname is saved (no cleanup needed)

#### Scenario: Local state directory

- **GIVEN** `.wt-control/.local-state/` does not exist
- **WHEN** `wt-control-sync` runs
- **THEN** the directory is created
- **AND** `.local-state/` is added to `.wt-control/.gitignore`

### Requirement: Usage Monitor Session Fallback

The system SHALL fetch Claude usage data with fallback session sources.

#### Scenario: Saved session works

- **GIVEN** a valid session key exists in `~/.set-core/claude-session.json`
- **WHEN** UsageWorker fetches usage data
- **THEN** the saved session is used for API calls

#### Scenario: Saved session invalid, browser fallback

- **GIVEN** saved session is missing or invalid (API call fails)
- **AND** user is logged into Claude in Chrome/Firefox
- **WHEN** UsageWorker fetches usage data
- **THEN** session key is read from browser cookies
- **AND** API call is made with browser session
- **AND** working session is saved to `claude-session.json`

#### Scenario: No session available

- **GIVEN** no saved session exists
- **AND** no browser session cookie found
- **WHEN** UsageWorker fetches usage data
- **THEN** `needs_login: true` is emitted
- **AND** usage bars show `--/5h` and `--/7d`

### Requirement: Qt Plugin Path Auto-Configuration

The GUI SHALL automatically configure Qt plugin path to avoid version conflicts.

#### Scenario: Conda Qt conflict

- **GIVEN** conda environment has different Qt version than PySide6
- **WHEN** GUI starts
- **THEN** `QT_PLUGIN_PATH` is set to PySide6's plugins directory
- **AND** GUI starts without "Could not find Qt platform plugin" error

### Requirement: Chat Message Notification in Project Header

The GUI SHALL display a blinking chat icon in the project header when there are unread messages.

#### Scenario: Unread messages indicator (per-project)

- **GIVEN** team sync is enabled
- **AND** there are unread chat messages for a specific project
- **WHEN** the worktree table is displayed
- **THEN** a "C" button appears in that project's header row
- **AND** the button blinks between orange and blue colors at 3x speed
- **AND** other projects without unread messages show no chat button

#### Scenario: Click chat icon

- **GIVEN** the chat icon is displayed in a project header
- **WHEN** the user clicks the "C" button
- **THEN** the chat dialog opens for that project

#### Scenario: No unread messages

- **GIVEN** team sync is enabled
- **AND** there are no unread chat messages for a project
- **WHEN** the worktree table is displayed
- **THEN** no chat icon is shown in that project's header

### Requirement: Chat Dialog Auto-Refresh

The chat dialog SHALL automatically refresh messages while open.

#### Scenario: Automatic refresh

- **GIVEN** the chat dialog is open
- **WHEN** 5 seconds elapse
- **THEN** messages are automatically fetched from the server
- **AND** new messages appear without manual refresh

#### Scenario: Manual refresh

- **GIVEN** the chat dialog is open
- **WHEN** the user clicks the refresh button
- **THEN** messages are immediately fetched

### Requirement: Project Menu in Worktree Context Menu

The GUI SHALL provide project-level actions in the worktree right-click menu.

#### Scenario: Project submenu

- **GIVEN** a worktree row is right-clicked
- **WHEN** the context menu appears
- **THEN** a "Project" submenu is available with:
  - Team Chat...
  - Generate Chat Key...
  - Team Settings...
  - Initialize wt-control...

#### Scenario: Generate Chat Key from context menu

- **GIVEN** the user selects "Generate Chat Key..." from the Project submenu
- **WHEN** the action is triggered
- **THEN** a chat key is generated for the worktree's project
- **AND** a confirmation dialog is shown

### Requirement: Consistent Project Detection

The GUI SHALL use consistent project detection across all dialogs.

#### Scenario: Settings and Chat use same project

- **GIVEN** worktrees are visible for project "my-project"
- **WHEN** Settings dialog opens
- **AND** Chat dialog opens
- **THEN** both dialogs use "my-project" as the active project

#### Scenario: Worktrees preferred over default

- **GIVEN** projects.json has default "project-a"
- **AND** worktrees are visible for "project-b"
- **WHEN** determining the active project
- **THEN** "project-b" is used (from worktrees)

#### Scenario: Fallback to default

- **GIVEN** no worktrees are visible
- **AND** projects.json has default "project-a"
- **WHEN** determining the active project
- **THEN** "project-a" is used (from default)

### Requirement: Cross-Machine Project Identification

The system SHALL identify projects across machines using git remote URL instead of local directory names.

#### Scenario: Remote URL in wt-status

- **GIVEN** a worktree exists at `/home/user/my-project-wt-feature`
- **AND** the git remote is `git@github.com:org/my-project.git`
- **WHEN** `wt-status --json` is called
- **THEN** output includes `remote_url: "git@github.com:org/my-project"` (without .git suffix)

#### Scenario: Match team worktrees by remote URL

- **GIVEN** local machine has project at `/home/alice/my-project`
- **AND** remote team member has same project at `/home/bob/code/my-project`
- **AND** both have same git remote URL
- **WHEN** team worktrees are displayed
- **THEN** Bob's worktrees appear under Alice's project (matched by remote_url)

#### Scenario: Different directory names, same project

- **GIVEN** Alice's directory is `aitools-specdriven`
- **AND** Bob's directory is `mediapipe-mirror`
- **AND** both point to same git remote
- **WHEN** team sync happens
- **THEN** worktrees are correctly grouped as same project

### Requirement: Config Merge with New Keys

The Config class SHALL properly merge loaded config files including new keys not in defaults.

#### Scenario: Load config with project-specific settings

- **GIVEN** DEFAULT_CONFIG has `team: {enabled: false, sync_interval_ms: 30000}`
- **AND** config file has `team: {projects: {"my-project": {enabled: true}}}`
- **WHEN** Config is loaded
- **THEN** `config.team["projects"]["my-project"]["enabled"]` is `true`
- **AND** new keys from config file are preserved (not ignored)

### Requirement: Table Re-rendering Cleanup

The GUI SHALL properly clean up previous render state before re-rendering the worktree table.

#### Scenario: Clear cell widgets on refresh

- **GIVEN** row 5 was a project header (with cell widget and span)
- **WHEN** refresh_table_display is called
- **AND** row 5 is now a regular worktree row
- **THEN** the cell widget is removed from row 5
- **AND** the span is reset to 1 column
- **AND** the row displays correctly as a worktree

#### Scenario: Team data triggers table refresh

- **GIVEN** team data was empty at startup
- **WHEN** TeamWorker emits new team data
- **THEN** update_team calls refresh_table_display
- **AND** team filter buttons and rows appear in project headers

### Requirement: wt-control-chat CLI

The system SHALL provide a CLI tool for reading and sending encrypted chat messages.

#### Scenario: Read messages

- **GIVEN** chat messages exist in `.wt-control/chat/messages.jsonl`
- **WHEN** user runs `wt-control-chat read`
- **THEN** messages are read and decrypted (if crypto available)
- **AND** displayed with timestamp, sender, recipient, and text

#### Scenario: Read messages as JSON

- **GIVEN** chat messages exist
- **WHEN** user runs `wt-control-chat --json read`
- **THEN** messages are output as JSON array with decrypted text

#### Scenario: Send message

- **GIVEN** recipient has chat_public_key in member file
- **AND** sender has chat key for project
- **WHEN** user runs `wt-control-chat send recipient "Hello"`
- **THEN** message is encrypted with recipient's public key
- **AND** appended to messages.jsonl with sender, recipient, enc, nonce
