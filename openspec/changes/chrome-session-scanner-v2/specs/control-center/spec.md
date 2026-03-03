## MODIFIED Requirements

### Requirement: Account management menu actions
The GUI SHALL provide menu actions to add and remove Claude accounts. The "Scan Chrome Sessions" action SHALL show install instructions when pycookiecheat is unavailable.

#### Scenario: Add account via menu
- **WHEN** user selects "Add Account..." from the menu
- **THEN** the main window hides (always-on-top conflict prevention)
- **AND** a dialog prompts for account name and session key
- **AND** the account is saved to `claude-session.json` with `"source": "manual"`
- **AND** the usage worker restarts to include the new account

#### Scenario: Remove account via menu
- **WHEN** user selects "Remove Account..." from the menu
- **AND** more than one account exists
- **THEN** a selection dialog lists all account names
- **AND** the selected account is removed from `claude-session.json`
- **AND** the usage worker restarts

#### Scenario: Remove action hidden for single account
- **WHEN** only one account is configured
- **THEN** the "Remove Account..." menu action SHALL NOT be visible

#### Scenario: Scan when pycookiecheat unavailable
- **WHEN** user selects "Scan Chrome Sessions" from the menu
- **AND** pycookiecheat is not installed
- **THEN** a warning dialog SHALL show install instructions including the pip command

#### Scenario: Toolbar scan button hidden when unavailable
- **WHEN** the Control Center initializes
- **AND** pycookiecheat is not installed
- **THEN** the toolbar scan button SHALL be hidden
- **AND** the menu "Scan Chrome Sessions" action SHALL remain visible
