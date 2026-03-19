## Why

The Control Center currently supports a single Claude session key, showing one pair of usage bars (5h/7d). Users who work with multiple Anthropic accounts (personal, work, different teams) must manually check each account's usage in the browser. Adding multi-account support lets users see all their accounts' usage side by side in the GUI.

## What Changes

- **Multi-account session storage**: Extend `claude-session.json` from `{"sessionKey": "..."}` to `{"accounts": [{"name": "...", "sessionKey": "..."}]}` with backward compatibility for the old single-key format
- **Parallel usage fetching**: `UsageWorker` fetches usage for all configured accounts in parallel, emitting a list of per-account usage data
- **Stacked usage rows in GUI**: Each account gets its own row with name label + 5h DualStripeBar + 7d DualStripeBar, displayed vertically in the existing usage area
- **Account management UI**: "Add Account" and "Remove Account" menu actions replace the current single "Set Session Key" action
- **Single-account backward compatibility**: When only one account exists (or old format detected), the UI renders identically to today — one row, no name label

## Capabilities

### New Capabilities
- `multi-account-usage`: Multi-account session key management, parallel usage fetching, and stacked per-account usage bar display in the Control Center GUI

### Modified Capabilities
- `usage-display`: Extend from single-account to N-account usage display — storage format, worker, and UI bar rendering

## Impact

- **Modified files**: `gui/workers/usage.py` (parallel multi-account fetch), `gui/control_center/main_window.py` (dynamic usage rows), `gui/control_center/mixins/handlers.py` (add/remove account dialogs), `gui/constants.py` (session file format)
- **Data format**: `~/.config/set-core/claude-session.json` evolves with backward compatibility
- **No new dependencies**: Reuses existing `DualStripeBar`, `curl-cffi`/curl/urllib fallback chain
- **No breaking changes**: Old single-key config auto-migrates on read
