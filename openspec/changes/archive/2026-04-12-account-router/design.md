# Design: account-router

## Context

Claude Code uses OAuth tokens stored in `~/.claude/.credentials.json` (accessToken, refreshToken, expiresAt, subscriptionType, rateLimitTier). This is separate from the web UI's sessionKey-based auth that set-control already manages via Chrome cookie scanning.

The set-control GUI already has a mature multi-account architecture: `gui/workers/usage.py` (UsageWorker with 30s polling), `gui/workers/chrome_cookies.py` (Chrome profile scanning), and `gui/control_center/` (stacked usage bars, account management menus). We extend this rather than build a parallel system.

Running CC instances read credentials at startup and hold the token in memory — swapping the file does not affect running processes. The sentinel starts CC agents as child processes, so each new agent picks up whatever credentials are on disk at launch time.

## Goals / Non-Goals

**Goals:**
- Manage multiple CC OAuth credential sets from CLI and GUI
- Provide usage visibility across all CC accounts
- Enable manual account switching with a single command
- Maintain ToS compliance — all switching is user-initiated

**Non-Goals:**
- Automatic rotation, scheduling, or daemon-based switching
- Proxy/MITM token injection
- CC token refresh (CC handles this internally)
- Web sessionKey ↔ CC OAuth token unification

## Decisions

### 1. Credentials swap over proxy

**Choice**: File swap of `~/.claude/.credentials.json`
**Over**: HTTPS proxy with header injection

The proxy approach (MITM with self-signed CA + `NODE_EXTRA_CA_CERTS`) would be transparent but adds significant complexity: TLS certificate management, proxy daemon lifecycle, and CC must be launched with special env vars. File swap is simpler, works with how the sentinel already launches agents, and doesn't affect running instances.

### 2. Separate account pool file

**Choice**: `~/.config/set-core/cc-accounts.json` for the pool
**Over**: Extending `claude-session.json` or storing in `~/.claude/`

The existing `claude-session.json` stores web sessionKeys — mixing OAuth tokens in would confuse the data model. Storing in `~/.claude/` could conflict with CC's own config management. A separate file keeps concerns clean and matches the set-core config pattern.

### 3. CLI name: `set-router`

**Choice**: Keep `set-router` as the CLI name despite the shift from "router" to "account manager"
**Over**: Renaming to `set-account` or `set-cc-account`

The name is already established in conversation and captures the intent (routing work to the right account). It's short and memorable. The --help text clarifies the actual function.

### 4. Reuse UsageWorker for CC accounts

**Choice**: Extend the existing `UsageWorker` in `gui/workers/usage.py` to handle both account types
**Over**: Creating a separate CC-specific usage worker

The polling logic, error isolation, and signal emission are identical. The only difference is the auth mechanism (sessionKey cookie vs OAuth Bearer token). Adding a `type` field to account dicts and branching the API call is cleaner than duplicating the worker.

### 5. File lock for swap safety

**Choice**: `fcntl.flock()` on credentials file during swap
**Over**: No locking, atomic rename, or external lock file

Atomic rename (`write temp → rename`) doesn't protect against two concurrent `set-router switch` calls. External lock files add cleanup burden. `fcntl.flock()` is simple, advisory (good enough for our use case), and automatically released on process exit.

## Risks / Trade-offs

**[Risk] CC changes credentials format** → We store the full JSON blob opaquely. If CC adds fields, they're preserved. If CC changes the file path, we need to update one constant.

**[Risk] Token expiry in pool** → Stored tokens may expire if unused for a long time. Mitigation: on switch, if the accessToken is expired but refreshToken is valid, CC will refresh on first use. If both are expired, `set-router status` shows "expired" and the user needs to `claude login` again.

**[Risk] Concurrent agent starts during swap** → The file lock window is <1ms (read JSON, write JSON). The sentinel starts agents sequentially. Race condition is theoretically possible but practically negligible.

**[Risk] Permissions regression** → File created with 600 but user might chmod. We verify and fix permissions on every write.

## Open Questions

- Should `set-router list` fetch live usage data (slow, ~2s per account) or show cached data from the last GUI poll? Initial implementation: cached with `--live` flag for fresh fetch.
