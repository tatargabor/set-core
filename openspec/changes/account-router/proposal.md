# Change: account-router

## Why

Running parallel agents (sentinel + N worktrees) burns through a single Claude Code account's 5-hour rate limit quickly. Currently there is no way to manage multiple CC accounts or see which account is active from the CLI. The set-control GUI already has multi-account support for web UI sessions (Chrome cookie scanning, usage monitoring), but Claude Code uses a separate OAuth-based auth system (`~/.claude/.credentials.json`) that is not managed at all.

Users with multiple legitimate CC subscriptions (personal + work, different orgs) need a way to:
1. Register multiple CC account credentials
2. See usage across all accounts
3. **Manually** switch the active account when approaching limits

**IMPORTANT**: This is an account management tool, NOT an automatic rotation system. Automatic rate-limit circumvention violates Anthropic's Terms of Service. The user decides when to switch. The tooling provides visibility and a convenient switch mechanism.

## What Changes

### 1. CC credentials management (`set-router` CLI)

New CLI tool for managing Claude Code account credentials:
- `set-router add "<name>"` — saves current `~/.claude/.credentials.json` as a named account
- `set-router remove "<name>"` — removes a saved account
- `set-router list` — shows all accounts with usage % and which is active
- `set-router switch "<name>"` — swaps `~/.claude/.credentials.json` to the selected account (no running CC instances affected — only new ones pick it up)
- `set-router status` — shows active account, usage %, time until reset

### 2. Account pool storage

New config file `~/.config/set-core/cc-accounts.json`:
```json
{
  "accounts": [
    {
      "name": "Personal",
      "credentials": { "accessToken": "...", "refreshToken": "...", ... },
      "source": "manual"
    },
    {
      "name": "Work",
      "credentials": { "accessToken": "...", "refreshToken": "...", ... },
      "source": "manual"
    }
  ],
  "active": "Personal"
}
```

Credentials are stored with the same security posture as `~/.claude/.credentials.json` (file permissions 600, plaintext — matching CC's own approach).

### 3. Usage monitoring for CC accounts

Extend the existing usage worker pattern to poll CC account usage via the same API endpoints. Reuses the multi-account polling architecture from `gui/workers/usage.py` but for OAuth tokens instead of sessionKeys.

### 4. set-control GUI integration

- Show CC accounts alongside web accounts in the usage panel
- Active CC account indicator
- "Switch CC Account" action (manual, user-initiated)
- Usage bars per CC account

### 5. Sentinel awareness (read-only)

The sentinel and CLI can query which account is active and its usage level. This enables:
- `set-router status` in scripts
- Sentinel log entries showing which account is being used
- Warning when active account is above 80% usage (informational only — no auto-switch)

## Capabilities

### New Capabilities
- `cc-account-manager` — CLI and library for managing multiple Claude Code OAuth credentials, manual switching, and usage visibility

### Modified Capabilities
- `multi-account-usage` — extend to support CC OAuth tokens alongside web sessionKeys

## Impact

- **New files**: `bin/set-router`, `lib/set_router/` (account pool, credentials swap, usage polling)
- **Modified**: `gui/workers/usage.py` (CC account type), `gui/control_center/` (CC account UI)
- **Config**: New `~/.config/set-core/cc-accounts.json`
- **Security**: Credentials stored at same security level as CC's own files (fs permissions only)
- **ToS compliance**: All switching is manual and user-initiated. Documentation explicitly warns against automation.

## Out of Scope

- **Automatic account rotation** — violates Anthropic ToS, will NOT be implemented
- **Proxy/MITM approach** — unnecessary complexity, credentials swap is sufficient
- **Token refresh automation** — CC handles its own token refresh; we just store/swap the credentials file
- **Chrome cookie → CC token conversion** — these are separate auth systems
