## 1. Account Pool Library

- [x] 1.1 Create `lib/set_router/__init__.py` with `AccountPool` class: load/save `cc-accounts.json`, add/remove/switch/list/status methods [REQ: cc-account-registration]
- [x] 1.2 Implement file permissions enforcement (600) on every save [REQ: account-pool-file-security]
- [x] 1.3 Implement `fcntl.flock()` credentials swap: lock `~/.claude/.credentials.json`, write, unlock [REQ: manual-cc-account-switch]
- [x] 1.4 Add account validation on add: read `~/.claude/.credentials.json`, verify it has accessToken/refreshToken fields [REQ: cc-account-registration]

## 2. CLI Tool

- [x] 2.1 Create `bin/set-router` shell wrapper (same pattern as `bin/set-control`) [REQ: cc-account-registration]
- [x] 2.2 Create `lib/set_router/cli.py` with argparse subcommands: add, remove, list, switch, status [REQ: cc-account-listing]
- [x] 2.3 Implement `set-router add "<name>"` — reads current credentials, stores in pool [REQ: cc-account-registration]
- [x] 2.4 Implement `set-router remove "<name>"` — removes from pool, handles active/last account edge cases [REQ: cc-account-removal]
- [x] 2.5 Implement `set-router list` — shows all accounts with usage %, active indicator [REQ: cc-account-listing]
- [x] 2.6 Implement `set-router switch "<name>"` — swaps credentials file with lock [REQ: manual-cc-account-switch]
- [x] 2.7 Implement `set-router status` — shows active account, usage, time until reset [REQ: cc-account-status]
- [x] 2.8 Add ToS compliance note to `--help` and switch output [REQ: tos-compliance-documentation]

## 3. Usage Monitoring Extension

- [x] 3.1 Add `"type": "cc"` / `"type": "web"` field to account dicts in `gui/workers/usage.py` [REQ: parallel-multi-account-usage-fetching]
- [x] 3.2 Extend `UsageWorker._fetch_usage_for_account()` to handle OAuth token auth (Bearer header) alongside sessionKey cookie auth [REQ: parallel-multi-account-usage-fetching]
- [x] 3.3 Load CC accounts from `cc-accounts.json` into the UsageWorker's account list alongside web accounts [REQ: parallel-multi-account-usage-fetching]
- [x] 3.4 Add `--live` flag to `set-router list` and `set-router status` for fresh API fetch (default: cached) [REQ: cc-account-status]

## 4. GUI Integration

- [x] 4.1 Add "[ACTIVE]" badge to CC account rows in the usage panel [REQ: stacked-per-account-usage-bars]
- [x] 4.2 Add right-click context menu on CC account rows: "Switch to this account" [REQ: stacked-per-account-usage-bars]
- [x] 4.3 Add "Switch CC Account..." menu action in hamburger menu (hidden if ≤1 CC account) [REQ: account-management-menu-actions]
- [x] 4.4 Wire switch action to `AccountPool.switch()` + restart UsageWorker + update badges [REQ: account-management-menu-actions]

## 5. Documentation

- [x] 5.1 Add `docs/account-manager.md` with setup guide, usage examples, and prominent ToS warning [REQ: tos-compliance-documentation]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN `set-router add "Personal"` THEN credentials saved to pool with 600 permissions [REQ: cc-account-registration, scenario: add-current-credentials-as-named-account]
- [x] AC-2: WHEN no `~/.claude/.credentials.json` exists THEN add fails with "Run claude login first" [REQ: cc-account-registration, scenario: add-fails-when-credentials-file-missing]
- [x] AC-3: WHEN `set-router switch "Work"` THEN credentials file swapped with lock, new instances use Work [REQ: manual-cc-account-switch, scenario: switch-to-existing-account]
- [x] AC-4: WHEN CC instance running with Account A AND switch to B THEN running instance unaffected [REQ: manual-cc-account-switch, scenario: running-cc-instances-unaffected-by-switch]
- [x] AC-5: WHEN `set-router list` THEN shows all accounts with usage % and active indicator [REQ: cc-account-listing, scenario: list-multiple-accounts]
- [x] AC-6: WHEN `set-router --help` THEN output includes ToS warning about manual-only use [REQ: tos-compliance-documentation, scenario: help-text-includes-tos-warning]
- [x] AC-7: WHEN polling cycle fires THEN CC accounts fetched via OAuth Bearer token [REQ: parallel-multi-account-usage-fetching, scenario: cc-accounts-fetched-via-oauth-token]
- [x] AC-8: WHEN right-click CC account row THEN context menu offers switch action [REQ: stacked-per-account-usage-bars, scenario: cc-account-switch-via-gui]
