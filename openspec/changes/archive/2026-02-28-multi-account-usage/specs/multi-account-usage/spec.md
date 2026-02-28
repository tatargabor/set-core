## ADDED Requirements

### Requirement: Multi-account session storage
The system SHALL store multiple Claude account session keys in a single configuration file with backward compatibility.

#### Scenario: New format with multiple accounts
- **WHEN** `claude-session.json` contains `{"accounts": [{"name": "Personal", "sessionKey": "sk-ant-..."}, {"name": "Work", "sessionKey": "sk-ant-..."}]}`
- **THEN** the system SHALL load all accounts and fetch usage for each

#### Scenario: Backward compatible migration from old format
- **WHEN** `claude-session.json` contains `{"sessionKey": "sk-ant-..."}`
- **THEN** the system SHALL treat it as a single account named "Default"
- **AND** usage fetching SHALL work identically to the old behavior

#### Scenario: No session file exists
- **WHEN** `claude-session.json` does not exist or contains no accounts
- **THEN** the system SHALL fall back to local JSONL parsing for a single unnamed account

#### Scenario: Write always uses new format
- **WHEN** the system saves account data
- **THEN** it SHALL always write the `{"accounts": [...]}` format
- **AND** SHALL never write the old `{"sessionKey": "..."}` format

### Requirement: Parallel multi-account usage fetching
The `UsageWorker` SHALL fetch usage data for all configured accounts in a single polling cycle.

#### Scenario: Fetch all accounts sequentially
- **WHEN** the 30-second polling cycle fires
- **THEN** the worker SHALL iterate through all configured accounts
- **AND** fetch usage data for each using the existing API fallback chain (curl-cffi → curl → urllib)
- **AND** emit a list of per-account usage dicts via the `usage_updated` signal

#### Scenario: Per-account error isolation
- **WHEN** one account's API call fails
- **THEN** that account's data SHALL show unavailable state ("--")
- **AND** other accounts SHALL NOT be affected

#### Scenario: Local-only fallback for zero accounts
- **WHEN** no accounts are configured
- **THEN** the worker SHALL fall back to local JSONL parsing
- **AND** emit a single-element list with `source: "local"` data

### Requirement: Stacked per-account usage bars
The Control Center SHALL display one usage row per configured account, stacked vertically.

#### Scenario: Multiple accounts displayed
- **WHEN** 2 or more accounts are configured with valid usage data
- **THEN** each account SHALL have its own row containing: name label + 5h DualStripeBar + 7d DualStripeBar
- **AND** rows SHALL be stacked vertically in the existing usage area

#### Scenario: Single account hides name label
- **WHEN** exactly 1 account is configured
- **THEN** the usage row SHALL NOT show a name label
- **AND** the layout SHALL be identical to the current single-account UI

#### Scenario: Dynamic row creation on account count change
- **WHEN** the number of accounts changes (add/remove)
- **THEN** the usage area SHALL rebuild its rows to match the new count
- **AND** existing color coding and tooltip behavior SHALL be preserved per row

### Requirement: Account management menu actions
The GUI SHALL provide menu actions to add and remove Claude accounts.

#### Scenario: Add account via menu
- **WHEN** user selects "Add Account..." from the menu
- **THEN** the main window hides (always-on-top conflict prevention)
- **AND** a dialog prompts for account name and session key
- **AND** the account is saved to `claude-session.json`
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
