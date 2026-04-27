# Cc Account Manager Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- CLI tool (`set-router`) for adding, removing, listing, and switching CC account credentials
- Account pool storage in `~/.config/set-core/cc-accounts.json`
- Credentials file swap (`~/.claude/.credentials.json`) on manual switch
- Usage visibility per CC account (session %, weekly %, burn rate)
- Active account indicator in CLI output
- File locking during credentials swap to prevent race conditions
- ToS compliance warnings in help text and documentation

### Out of scope
- Automatic account rotation or scheduling
- Token refresh (CC handles this internally)
- Proxy/MITM interception of CC API calls
- Chrome cookie to OAuth token conversion
- Web UI sessionKey management (handled by existing multi-account-usage)

## Requirements

### Requirement: CC account registration
The system SHALL allow users to register Claude Code account credentials from the current `~/.claude/.credentials.json` as a named account in the account pool.

#### Scenario: Add current credentials as named account
- **WHEN** user runs `set-router add "Personal"`
- **THEN** the system SHALL read `~/.claude/.credentials.json`
- **AND** store its contents under the name "Personal" in `~/.config/set-core/cc-accounts.json`
- **AND** set file permissions to 600 on the account pool file
- **AND** if no active account is set, mark this account as active

#### Scenario: Add fails when credentials file missing
- **WHEN** user runs `set-router add "Work"`
- **AND** `~/.claude/.credentials.json` does not exist
- **THEN** the system SHALL exit with error: "No Claude Code credentials found. Run `claude login` first."

#### Scenario: Add with duplicate name overwrites
- **WHEN** user runs `set-router add "Personal"`
- **AND** an account named "Personal" already exists
- **THEN** the system SHALL overwrite the stored credentials with the current ones
- **AND** display a warning: "Updated existing account 'Personal'"

### Requirement: CC account removal
The system SHALL allow users to remove a named account from the pool.

#### Scenario: Remove existing account
- **WHEN** user runs `set-router remove "Work"`
- **AND** an account named "Work" exists
- **THEN** the system SHALL remove it from `cc-accounts.json`

#### Scenario: Remove active account
- **WHEN** user runs `set-router remove "Personal"`
- **AND** "Personal" is the active account
- **AND** other accounts exist
- **THEN** the system SHALL remove the account
- **AND** set the next available account as active
- **AND** swap `~/.claude/.credentials.json` to the new active account

#### Scenario: Remove last account
- **WHEN** user runs `set-router remove "Personal"`
- **AND** "Personal" is the only account
- **THEN** the system SHALL exit with error: "Cannot remove the last account"

#### Scenario: Remove non-existent account
- **WHEN** user runs `set-router remove "Ghost"`
- **AND** no account named "Ghost" exists
- **THEN** the system SHALL exit with error: "Account 'Ghost' not found"

### Requirement: CC account listing
The system SHALL display all registered accounts with their usage status and active indicator.

#### Scenario: List multiple accounts
- **WHEN** user runs `set-router list`
- **AND** accounts "Personal" (active, 78% session) and "Work" (12% session) exist
- **THEN** the system SHALL display:
  ```
  ● Personal  session: 78%  weekly: 34%  [ACTIVE]
  ○ Work      session: 12%  weekly:  5%
  ```

#### Scenario: List with no accounts
- **WHEN** user runs `set-router list`
- **AND** no accounts are registered
- **THEN** the system SHALL display: "No accounts registered. Run `claude login` then `set-router add <name>`."

### Requirement: Manual CC account switch
The system SHALL swap the active CC credentials file when the user explicitly requests a switch. Running CC instances SHALL NOT be affected.

#### Scenario: Switch to existing account
- **WHEN** user runs `set-router switch "Work"`
- **AND** an account named "Work" exists
- **THEN** the system SHALL acquire a file lock on `~/.claude/.credentials.json`
- **AND** write the "Work" account's credentials to `~/.claude/.credentials.json`
- **AND** update `cc-accounts.json` to mark "Work" as active
- **AND** release the lock
- **AND** display: "Switched to 'Work'. New CC instances will use this account."

#### Scenario: Switch to non-existent account
- **WHEN** user runs `set-router switch "Ghost"`
- **AND** no account named "Ghost" exists
- **THEN** the system SHALL exit with error: "Account 'Ghost' not found"

#### Scenario: Switch to already active account
- **WHEN** user runs `set-router switch "Personal"`
- **AND** "Personal" is already active
- **THEN** the system SHALL display: "'Personal' is already the active account."

#### Scenario: Running CC instances unaffected by switch
- **WHEN** a CC instance is running with Account A credentials
- **AND** user switches to Account B
- **THEN** the running CC instance SHALL continue using Account A (in-memory token)
- **AND** only new CC instances started after the switch SHALL use Account B

### Requirement: CC account status
The system SHALL provide a quick status view of the active account including usage and time until reset.

#### Scenario: Status with active account
- **WHEN** user runs `set-router status`
- **AND** "Personal" is active at 78% session usage
- **THEN** the system SHALL display:
  ```
  Active: Personal
  Session: 78% (resets in 2h 15m)
  Weekly:  34% (resets in 4d 12h)
  ⚠ Session usage above 80% — consider switching accounts
  ```

#### Scenario: Status with no accounts
- **WHEN** user runs `set-router status`
- **AND** no accounts are registered
- **THEN** the system SHALL display: "No accounts registered."

### Requirement: ToS compliance documentation
The system SHALL include prominent warnings that automatic account rotation violates Anthropic's Terms of Service.

#### Scenario: Help text includes ToS warning
- **WHEN** user runs `set-router --help`
- **THEN** the output SHALL include: "NOTE: This tool is for manual account management only. Automatic rotation to circumvent rate limits violates Anthropic's Terms of Service."

#### Scenario: Switch command reminds about manual use
- **WHEN** user runs `set-router switch`
- **THEN** the output SHALL include a brief note: "Manual switch — automatic rotation is not supported."

### Requirement: Account pool file security
The account pool file SHALL be created with restrictive permissions since it contains OAuth tokens.

#### Scenario: New file created with 600 permissions
- **WHEN** `cc-accounts.json` is created for the first time
- **THEN** the file SHALL have permissions 600 (owner read/write only)

#### Scenario: Existing file permissions preserved on update
- **WHEN** `cc-accounts.json` is updated
- **THEN** the system SHALL verify permissions are 600
- **AND** fix them if they have been changed
