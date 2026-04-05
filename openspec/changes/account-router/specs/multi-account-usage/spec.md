## MODIFIED Requirements

### Requirement: Parallel multi-account usage fetching
The `UsageWorker` SHALL fetch usage data for all configured accounts in a single polling cycle. This includes both web UI session accounts (sessionKey-based) AND Claude Code accounts (OAuth token-based) from the CC account pool.

#### Scenario: Fetch all accounts sequentially
- **WHEN** the 30-second polling cycle fires
- **THEN** the worker SHALL iterate through all configured accounts (both web and CC)
- **AND** fetch usage data for each using the appropriate auth mechanism
- **AND** emit a list of per-account usage dicts via the `usage_updated` signal

#### Scenario: Per-account error isolation
- **WHEN** one account's API call fails
- **THEN** that account's data SHALL show unavailable state ("--")
- **AND** other accounts SHALL NOT be affected

#### Scenario: Local-only fallback for zero accounts
- **WHEN** no accounts are configured (neither web nor CC)
- **THEN** the worker SHALL fall back to local JSONL parsing
- **AND** emit a single-element list with `source: "local"` data

#### Scenario: CC accounts fetched via OAuth token
- **WHEN** the polling cycle processes a CC account
- **THEN** the worker SHALL use the stored OAuth accessToken for API authentication
- **AND** the usage response SHALL include the same fields as web accounts (session_pct, weekly_pct, burn rates)

#### Scenario: CC accounts distinguished in output
- **WHEN** usage data is emitted for a CC account
- **THEN** the entry SHALL include `"type": "cc"` to distinguish from `"type": "web"` accounts

### Requirement: Stacked per-account usage bars
The Control Center SHALL display one usage row per configured account, stacked vertically. CC accounts SHALL show an active indicator and a manual switch action.

#### Scenario: Multiple accounts displayed
- **WHEN** 2 or more accounts are configured with valid usage data
- **THEN** each account SHALL have its own row containing: name label + 5h DualStripeBar + 7d DualStripeBar
- **AND** rows SHALL be stacked vertically in the existing usage area

#### Scenario: CC accounts show active badge
- **WHEN** a CC account row is displayed
- **AND** that account is the active CC account
- **THEN** the row SHALL show an "[ACTIVE]" badge next to the name

#### Scenario: CC account switch via GUI
- **WHEN** user right-clicks a CC account row
- **THEN** a context menu SHALL offer "Switch to this account"
- **AND** clicking it SHALL call the credentials swap logic
- **AND** update the active badge

#### Scenario: Single account hides name label
- **WHEN** exactly 1 account is configured (across all types)
- **THEN** the usage row SHALL NOT show a name label
- **AND** the layout SHALL be identical to the current single-account UI

#### Scenario: Dynamic row creation on account count change
- **WHEN** the number of accounts changes (add/remove)
- **THEN** the usage area SHALL rebuild its rows to match the new count
- **AND** existing color coding and tooltip behavior SHALL be preserved per row

### Requirement: Account management menu actions
The GUI SHALL provide menu actions to add and remove Claude accounts. CC account management actions SHALL be available alongside web account actions.

#### Scenario: Switch CC account via menu
- **WHEN** user selects "Switch CC Account..." from the menu
- **AND** multiple CC accounts exist
- **THEN** a selection dialog SHALL list all CC account names with usage %
- **AND** the selected account SHALL become the active CC account
- **AND** `~/.claude/.credentials.json` SHALL be updated

#### Scenario: Switch CC action hidden for single CC account
- **WHEN** only one CC account is registered
- **THEN** the "Switch CC Account..." menu action SHALL NOT be visible
