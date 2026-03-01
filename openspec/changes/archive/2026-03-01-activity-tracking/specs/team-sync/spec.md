## MODIFIED Requirements

### Requirement: Member Status Sync

The system SHALL synchronize member status via the wt-control branch.

#### Scenario: Sync local status

- **GIVEN** wt-control is initialized
- **WHEN** the user runs `wt-control-sync`
- **THEN** member status is written to `members/{name}.json`
- **AND** the JSON includes: name, display_name, hostname, status, changes, last_seen

#### Scenario: Sync includes activity data

- **GIVEN** wt-control is initialized
- **AND** a worktree has `.claude/activity.json` with skill and broadcast data
- **WHEN** `wt-control-sync` runs
- **THEN** the corresponding change entry in `members/{name}.json` SHALL include an `activity` block
- **AND** the activity block contains: `skill`, `skill_args`, `broadcast`, `updated_at` from the activity file

#### Scenario: Activity file missing for worktree

- **GIVEN** a worktree does not have `.claude/activity.json`
- **WHEN** `wt-control-sync` reads activity for that worktree
- **THEN** the change entry has `activity: null`

#### Scenario: Activity file stale

- **GIVEN** a worktree has `.claude/activity.json` with `updated_at` older than 5 minutes
- **WHEN** `wt-control-sync` reads activity
- **THEN** the activity is still included in the member JSON
- **AND** consumers use `updated_at` to judge freshness

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

### MODIFIED Requirements

### Requirement: Team Worktree Details Dialog

The system SHALL provide a dialog to view team worktree details.

#### Scenario: Open details dialog

- **GIVEN** a team row is selected
- **WHEN** the user clicks "View Details..." from context menu
- **THEN** a dialog opens showing:
  - Member name and hostname
  - Change ID
  - Agent status
  - Last seen timestamp
  - Last activity description (if available)
  - Active skill name and args (if activity data present)
  - Broadcast message (if set)

#### Scenario: Close details dialog

- **GIVEN** the details dialog is open
- **WHEN** the user clicks "Close" or presses Escape
- **THEN** the dialog closes
- **AND** no changes are made

### Requirement: Team row tooltip

The GUI SHALL show activity information in team row tooltips.

#### Scenario: Team row tooltip with activity

- **GIVEN** team worktrees are displayed
- **AND** a team member has activity data (skill, broadcast)
- **WHEN** the user hovers over a team row
- **THEN** a tooltip shows:
  - Full member name (display_name)
  - Change ID
  - Agent status
  - Active skill (e.g., "opsx:apply add-oauth")
  - Broadcast message (if set)
  - Last seen (relative time, e.g., "2 min ago")

#### Scenario: Team row tooltip without activity

- **GIVEN** team worktrees are displayed
- **AND** a team member has no activity data
- **WHEN** the user hovers over a team row
- **THEN** a tooltip shows the existing fields (name, change ID, agent status, last seen)
- **AND** no skill or broadcast line is shown
