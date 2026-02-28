# usage-display Specification

## Purpose
Display Claude usage statistics in the Control Center GUI, showing session (5h) and weekly capacity percentages with time remaining until reset.
## Requirements
### Requirement: Display Claude Capacity Statistics
The Control Center GUI SHALL display Claude Code capacity statistics via dual progress bars — a time-elapsed bar above a usage bar for each time window (5h session, 7d weekly).

#### Scenario: Dual bars displayed per time window
Given the Control Center is running
And usage data is available from the API
When the GUI refreshes
Then each time window (5h, 7d) SHALL display two bars stacked vertically with 0px gap:
  - Top bar: time-elapsed percentage (how far through the window)
  - Bottom bar: usage percentage (how much quota consumed)

#### Scenario: Display format with comma separator
Given usage data is available from the API
When displaying session usage
Then the time label SHALL show format like "60%, 2h" (time-elapsed percentage, comma, remaining time)
And the usage label SHALL show format like "42%" (usage percentage only)
And weekly time label SHALL show format like "71%, 2d" (time-elapsed percentage, comma, remaining time)
And weekly usage label SHALL show format like "55%" (usage percentage only)

#### Scenario: Local-only data shows unknown state
Given usage data comes from local JSONL parsing (no session key)
When displaying capacity
Then time labels SHALL show "--"
And usage labels SHALL show "--/5h" and "--/7d"
And all four progress bars SHALL remain empty
And tooltips show token counts and suggest setting session key

#### Scenario: Burn-rate-relative color coding
Given usage data is available from the API
When usage percentage is more than 5 points below time-elapsed percentage
Then the usage bar SHALL be displayed in green (under pace)
When usage percentage is within 5 points of time-elapsed percentage
Then the usage bar SHALL be displayed in yellow (on pace)
When usage percentage is more than 5 points above time-elapsed percentage
Then the usage bar SHALL be displayed in red (over pace)

#### Scenario: Time bar color
Given usage data is available from the API
When displaying the time-elapsed bar
Then the time bar SHALL use a neutral color (`bar_time` theme color) regardless of percentage

#### Scenario: Graceful fallback when data unavailable
Given usage data cannot be fetched from any source
When the GUI attempts to display capacity
Then it displays "--" for time labels and "--/5h", "--/7d" for usage labels
And all four bars remain empty
And does not show errors to the user

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

### Requirement: GUI session key input dialog
The GUI SHALL provide menu actions to manage multiple Claude account session keys.

#### Scenario: Add account via menu
- **WHEN** user selects "Add Account..." from the menu
- **THEN** the main window hides to prevent always-on-top conflicts
- **AND** a dialog prompts for account name and session key
- **AND** the entered account is appended to `~/.config/wt-tools/claude-session.json`
- **AND** the main window reappears after the dialog closes

#### Scenario: Remove account via menu
- **WHEN** user selects "Remove Account..." from the menu
- **AND** more than one account exists
- **THEN** a selection dialog lists all account names
- **AND** the selected account is removed from `~/.config/wt-tools/claude-session.json`

#### Scenario: Backward compatible with old single-key format
- **WHEN** `claude-session.json` contains old format `{"sessionKey": "..."}`
- **THEN** the system reads it as a single account named "Default"

### Requirement: Cost estimation support
The `UsageCalculator` SHALL support estimated USD cost calculation.

#### Scenario: Cost calculated per model
- **WHEN** usage data includes model names
- **THEN** cost is calculated using per-model token prices
- **AND** unknown models use a conservative default price

#### Scenario: Cost available in summary
- **WHEN** `get_usage_summary()` is called
- **THEN** the returned dict includes `estimated_cost_usd` field

### Requirement: Background Usage Data Fetching
Usage data SHALL be fetched periodically in a background thread to avoid blocking the UI.

#### Scenario: Periodic data refresh
Given the Control Center is running
When 30 seconds have elapsed since the last fetch
Then the usage worker fetches fresh data
And updates the progress bars

### Requirement: Cross-Platform Support
Usage tracking SHALL work on Linux, macOS, and Windows.

#### Scenario: Cross-platform paths
Given the application runs on any supported OS
When accessing Claude data
Then it uses `pathlib.Path.home() / ".claude"` for the Claude directory
And handles missing directories gracefully

### Requirement: Time-Elapsed Percentage Calculation
The GUI SHALL calculate how far through each time window the user currently is, derived from the reset timestamp.

#### Scenario: Time-elapsed from reset timestamp
- **WHEN** the API returns a `session_reset` or `weekly_reset` ISO timestamp
- **THEN** the time-elapsed percentage SHALL be calculated as: `(now - (reset - window)) / window * 100`
- **AND** the result SHALL be clamped to 0-100%

#### Scenario: 5h session window
- **WHEN** calculating time-elapsed for the session bar
- **THEN** the window size SHALL be 5 hours

#### Scenario: 7d weekly window
- **WHEN** calculating time-elapsed for the weekly bar
- **THEN** the window size SHALL be 7 days (168 hours)

### Requirement: Time Bar Theme Color
A new `bar_time` color SHALL be added to all theme color profiles.

#### Scenario: Theme color values
- **WHEN** rendering the time-elapsed bar
- **THEN** the bar color SHALL use `bar_time` from the active theme
- **AND** `bar_time` SHALL be a muted neutral tone (slate/gray family) in all themes

## Implementation Notes

### Files
- `gui/usage_calculator.py` - Local JSONL token usage calculator
- `gui/workers/usage.py` - Background worker for usage fetching (curl-cffi primary, curl/urllib fallback)
- `gui/constants.py` - Default usage limits configuration

### Removed
- `cloudscraper` - Replaced by `curl-cffi` (Chrome TLS fingerprint impersonation)
- `browser_cookie3` - Removed due to cross-platform unreliability
- WebEngine Login Dialog - Replaced by simple QInputDialog paste flow

### Requirement: Clean worker shutdown

All background worker threads (StatusWorker, UsageWorker, TeamWorker, ChatWorker) SHALL be stopped before application exit.

The `quit_app()` and `restart_app()` methods SHALL use centralized `_stop_all_workers()` and `_wait_all_workers()` helpers that handle all workers uniformly.

#### Scenario: All workers stopped on quit

- **WHEN** user quits the application via tray menu
- **THEN** all worker threads SHALL be signaled to stop
- **AND** the application SHALL wait up to 2 seconds for each worker to finish
- **AND** workers that don't finish in time SHALL be terminated

#### Scenario: UsageWorker responds to stop within 500ms

- **WHEN** `usage_worker.stop()` is called
- **THEN** the UsageWorker thread SHALL exit its sleep loop within 500ms
- **AND** the thread SHALL terminate cleanly without requiring `QThread.terminate()`

### Requirement: Interruptible worker sleep

The UsageWorker SHALL use interruptible sleep (small chunks checking `_running` flag) instead of a single 30-second `msleep()` call. This ensures `stop()` takes effect promptly.

#### Scenario: Sleep interrupted by stop

- **WHEN** UsageWorker is sleeping between fetch cycles
- **AND** `stop()` is called
- **THEN** the worker SHALL wake and exit within 500ms
