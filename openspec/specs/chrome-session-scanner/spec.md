# Chrome Session Scanner Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Chrome profile discovery
The system SHALL discover all Chrome profiles on the local machine by scanning the platform-specific Chrome user data directory.

#### Scenario: Discover profiles on Linux
- **WHEN** the scanner runs on Linux
- **THEN** it SHALL scan `~/.config/google-chrome/` for profile directories (Default, Profile 1, Profile 2, etc.)
- **AND** each directory containing a `Preferences` file SHALL be treated as a valid profile

#### Scenario: Discover profiles on macOS
- **WHEN** the scanner runs on macOS
- **THEN** it SHALL scan `~/Library/Application Support/Google/Chrome/` for profile directories
- **AND** each directory containing a `Preferences` file SHALL be treated as a valid profile

#### Scenario: No Chrome installation found
- **WHEN** the Chrome user data directory does not exist
- **THEN** the scanner SHALL return an empty list
- **AND** no error SHALL be raised

### Requirement: Profile name resolution
The system SHALL resolve a human-readable name for each Chrome profile.

#### Scenario: Google account name available
- **WHEN** the profile's `Preferences` JSON contains `account_info[0].full_name`
- **THEN** the scanner SHALL use that value as the account name
- **AND** append the profile directory name in parentheses (e.g. "John Doe (Profile 1)")

#### Scenario: Chrome profile name fallback
- **WHEN** the profile's `Preferences` JSON does not contain `account_info` but contains `profile.name`
- **THEN** the scanner SHALL use the `profile.name` value as the account name

#### Scenario: Directory name fallback
- **WHEN** the profile's `Preferences` JSON contains neither `account_info` nor `profile.name`
- **THEN** the scanner SHALL use the profile directory name as the account name (e.g. "Default", "Profile 1")

### Requirement: Session cookie extraction
The system SHALL extract the `sessionKey` cookie for `claude.ai` from each Chrome profile's cookie database.

#### Scenario: Session cookie found and decrypted
- **WHEN** a Chrome profile has a `sessionKey` cookie for `.claude.ai`
- **THEN** the scanner SHALL decrypt the cookie value using `pycookiecheat`
- **AND** include it in the results as `{"name": "<resolved name>", "sessionKey": "<decrypted value>"}`

#### Scenario: No session cookie in profile
- **WHEN** a Chrome profile does not have a `sessionKey` cookie for `claude.ai`
- **THEN** that profile SHALL be skipped (not included in results)

#### Scenario: Cookie decryption fails
- **WHEN** cookie decryption fails for a profile (keyring locked, permissions, etc.)
- **THEN** that profile SHALL be skipped
- **AND** the error SHALL be logged but not shown to the user

### Requirement: Graceful degradation without pycookiecheat
The system SHALL handle the absence of the `pycookiecheat` dependency gracefully.

#### Scenario: pycookiecheat not installed
- **WHEN** `pycookiecheat` is not installed
- **AND** the user triggers a Chrome session scan
- **THEN** the system SHALL show a warning dialog with install instructions: "pip install pycookiecheat"
- **AND** the scan SHALL not proceed

#### Scenario: Toolbar and menu still visible
- **WHEN** `pycookiecheat` is not installed
- **THEN** the scan toolbar button and menu item SHALL still be visible and clickable
- **AND** clicking them SHALL show the install instructions dialog

### Requirement: Account list replacement on scan
The system SHALL replace the entire account list in `claude-session.json` with scan results.

#### Scenario: Scan finds sessions
- **WHEN** the scanner finds one or more valid session cookies
- **THEN** the system SHALL overwrite the accounts list in `claude-session.json` with the scan results
- **AND** restart the usage worker to fetch data for the new accounts

#### Scenario: Scan finds no sessions
- **WHEN** the scanner finds no valid session cookies across any Chrome profile
- **THEN** the system SHALL show an informational dialog: "No Chrome profiles with Claude sessions found"
- **AND** the existing account list SHALL NOT be modified

### Requirement: Toolbar scan button
The system SHALL provide a toolbar button for triggering Chrome session scanning.

#### Scenario: Button placement and appearance
- **WHEN** the Control Center window is displayed
- **THEN** a scan button with icon `🔍` SHALL appear in the bottom button bar
- **AND** it SHALL be placed between the active filter button and the minimize button
- **AND** it SHALL have a tooltip "Scan Chrome Sessions"

#### Scenario: Button triggers scan
- **WHEN** the user clicks the scan button
- **THEN** the Chrome session scan SHALL execute
- **AND** results SHALL update the account list and usage display

### Requirement: Menu scan action
The system SHALL provide a menu item for triggering Chrome session scanning.

#### Scenario: Menu item in main menu
- **WHEN** the user opens the hamburger menu (≡)
- **THEN** a "Scan Chrome Sessions" action SHALL appear after "Add Account..."
- **AND** clicking it SHALL trigger the same scan as the toolbar button

### Requirement: Auto-scan on startup
The system SHALL automatically scan Chrome sessions when the application starts.

#### Scenario: Startup auto-scan with delay
- **WHEN** the Control Center application starts
- **THEN** a Chrome session scan SHALL execute after a 2-second delay
- **AND** results SHALL populate the account list silently (no dialogs on success)

#### Scenario: Auto-scan failure is silent
- **WHEN** the startup auto-scan fails (no Chrome, no pycookiecheat, no sessions)
- **THEN** no error dialog SHALL be shown
- **AND** the existing account list (if any) SHALL remain unchanged
