## MODIFIED Requirements

### Requirement: GUI session key input dialog
The GUI SHALL provide menu actions to manage multiple Claude account session keys.

#### Scenario: Add account via menu
- **WHEN** user selects "Add Account..." from the menu
- **THEN** the main window hides to prevent always-on-top conflicts
- **AND** a dialog prompts for account name and session key
- **AND** the entered account is appended to `~/.config/set-core/claude-session.json`
- **AND** the main window reappears after the dialog closes

#### Scenario: Remove account via menu
- **WHEN** user selects "Remove Account..." from the menu
- **AND** more than one account exists
- **THEN** a selection dialog lists all account names
- **AND** the selected account is removed from `~/.config/set-core/claude-session.json`

#### Scenario: Backward compatible with old single-key format
- **WHEN** `claude-session.json` contains old format `{"sessionKey": "..."}`
- **THEN** the system reads it as a single account named "Default"

### Requirement: Display Claude Capacity Statistics
The Control Center GUI SHALL display Claude Code capacity statistics via progress bars for each configured account.

#### Scenario: Capacity displayed via progress bars
Given the Control Center is running
And usage data is available from the API
When the GUI refreshes
Then it displays one row per account, each with 5h and 7d DualStripeBar progress bars

#### Scenario: Single account matches current layout
Given exactly one account is configured
When displaying capacity
Then the layout is identical to the current single-row design (no name label)

#### Scenario: Multiple accounts show name labels
Given two or more accounts are configured
When displaying capacity
Then each row shows the account name followed by the 5h and 7d bars

#### Scenario: Local-only data shows unknown state
Given no accounts are configured (no session keys)
When displaying capacity
Then a single row shows "--/5h" and "--/7d" labels with empty bars
And tooltips show token counts and suggest adding an account

### Requirement: Usage Data Sources
Usage data SHALL be fetched from multiple sources with automatic fallback, supporting multiple accounts.

#### Scenario: Multi-account fetch cycle
Given multiple accounts are configured with session keys
When the 30-second polling cycle fires
Then the worker fetches usage for each account using the existing fallback chain
And emits a list of per-account usage dicts

#### Scenario: Per-account error isolation
Given multiple accounts are configured
When one account's API call fails
Then that account shows "--" state
And other accounts continue showing their data normally
