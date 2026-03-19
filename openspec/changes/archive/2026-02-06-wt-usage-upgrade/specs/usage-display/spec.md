## MODIFIED Requirements

### Requirement: Usage Data Sources
Usage data SHALL be fetched from multiple sources with automatic fallback.

#### Scenario: Primary - Claude.ai API
Given a saved session key exists in `~/.config/set-core/claude-session.json`
When fetching usage data
Then the worker calls the claude.ai organizations API using stdlib `urllib.request`
And retrieves exact utilization percentages and reset times

#### Scenario: Fallback - Local JSONL Parsing
Given no session key is available or API call fails
When fetching usage data
Then the worker parses `~/.claude/projects/*/*.jsonl` files
And calculates token usage for 5h and 7d windows
And estimates percentages based on configurable limits

#### Scenario: Configurable estimation limits
Given local JSONL parsing is used
When calculating percentages
Then `usage.estimated_5h_limit` config (default 500000) is used for 5h percentage
And `usage.estimated_weekly_limit` config (default 5000000) is used for weekly percentage

#### Scenario: Cloudflare fallback
Given the `urllib.request` call is blocked by Cloudflare
When fetching usage data from claude.ai API
Then the worker attempts the same request via `curl` subprocess
And if both fail, falls back to local JSONL parsing

## ADDED Requirements

### Requirement: GUI session key input dialog
The GUI SHALL provide a menu option to set the Claude session key via a simple input dialog.

#### Scenario: Set session key via menu
- **WHEN** user selects "Set Session Key..." from the menu
- **THEN** a `QInputDialog` appears prompting for the session key
- **AND** the entered key is saved to `~/.config/set-core/claude-session.json`

#### Scenario: Session key validation in GUI
- **WHEN** user enters a session key in the dialog
- **THEN** the system tests the key with an API call
- **AND** shows success or failure feedback

### Requirement: Cost estimation support
The `UsageCalculator` SHALL support estimated USD cost calculation.

#### Scenario: Cost calculated per model
- **WHEN** usage data includes model names
- **THEN** cost is calculated using per-model token prices
- **AND** unknown models use a conservative default price

#### Scenario: Cost available in summary
- **WHEN** `get_usage_summary()` is called
- **THEN** the returned dict includes `estimated_cost_usd` field

## REMOVED Requirements

### Requirement: WebEngine Login Dialog
**Reason**: Replaced by simple QInputDialog paste flow. WebEngine was a heavy dependency with unreliable Cloudflare bypass.
**Migration**: Use "Set Session Key..." menu item or `wt-usage --login` CLI command.
