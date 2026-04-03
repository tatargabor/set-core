# Proposal: Filter Expired Chrome Sessions

## Why

The Chrome session scanner includes expired/invalidated sessions in results because it only checks whether a `sessionKey` cookie exists in Chrome's cookie store — it never validates that the session is still active server-side. These dead sessions then appear in the usage display as permanently unavailable accounts, cluttering the UI and wasting API calls every 30-second poll cycle.

## What Changes

- **Refactor `_fetch_org_name()` to return validation status alongside org name** — distinguish between "session expired" (401/403), "session valid" (200 + org data), and "network error" (timeout/connection failure)
- **Filter expired sessions during scan** — sessions that get a definitive auth error are excluded from results
- **Keep network-error sessions with an "unverified" marker** — transient failures shouldn't permanently drop a session
- **Add consecutive-failure tracking in UsageWorker** — sessions that fail N consecutive polls get flagged as expired in the UI

## Capabilities

### Modified Capabilities

- `chrome-session-scanner` — adding session validation during scan, changing the org fetch to return structured status

### New Capabilities

- (none)

## Impact

- `gui/workers/chrome_cookies.py` — `_fetch_org_name()` refactored to `_validate_session()`, `scan_chrome_sessions()` filters based on validation result
- `gui/workers/usage.py` — `UsageWorker` tracks consecutive failures per account
- `tests/gui/test_17_chrome_cookies.py` — new test cases for validation filtering
