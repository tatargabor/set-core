## 1. Session storage format

- [x] 1.1 Add `load_accounts()` helper to `gui/workers/usage.py` that reads `claude-session.json`, detects old `{"sessionKey"}` format and auto-wraps into `{"accounts": [...]}`, returns list of `{"name", "sessionKey"}` dicts
- [x] 1.2 Add `save_accounts(accounts)` helper that writes the new `{"accounts": [...]}` format atomically
- [x] 1.3 Update `UsageWorker._load_session()` to use `load_accounts()` instead of reading single key

## 2. Multi-account usage fetching

- [x] 2.1 Change `UsageWorker.usage_updated` signal from `Signal(dict)` to `Signal(list)` — emits list of per-account usage dicts
- [x] 2.2 Update `UsageWorker.run()` loop to iterate all accounts, calling `fetch_claude_api_usage()` per account, collecting results into a list
- [x] 2.3 Add per-account error isolation — failed accounts get `{"name": ..., "available": False}` without affecting others
- [x] 2.4 Preserve local-only fallback when zero accounts configured — emit single-element list with `source: "local"` data

## 3. Dynamic usage bar UI

- [x] 3.1 Replace static `usage_5h_bar`/`usage_7d_bar`/label attrs in `main_window.py` with `self.usage_container` (QVBoxLayout) and `self.account_widgets` list
- [x] 3.2 Add `_rebuild_usage_rows(count)` method that creates/destroys rows dynamically — each row: name QLabel + 5h label + 5h DualStripeBar + 7d label + 7d DualStripeBar
- [x] 3.3 Update `update_usage_bars()` to accept list data, iterate per-account, call `_rebuild_usage_rows()` if count changed
- [x] 3.4 Hide name label when exactly 1 account (identical to current single-account layout)
- [x] 3.5 Preserve existing color coding (`_burn_rate_color`), tooltips, and time-remaining calculations per row

## 4. Account management menu

- [x] 4.1 Replace "Set Session Key..." menu action with "Add Account..." in `handlers.py`
- [x] 4.2 Implement `show_add_account()` — two-field dialog (name + session key), appends to accounts list, saves, restarts worker
- [x] 4.3 Add "Remove Account..." menu action (visible only when >1 account)
- [x] 4.4 Implement `show_remove_account()` — list selection dialog, removes selected, saves, restarts worker

## 5. Theme and layout polish

- [x] 5.1 Update `apply_theme()` to clear/reset usage rows on theme change (call `_rebuild_usage_rows`)
- [x] 5.2 Ensure account name labels use the current theme's text color and small font size

## 6. Tests

- [x] 6.1 Add tests for `load_accounts()` — old format migration, new format, missing file, empty accounts
- [x] 6.2 Add tests for `save_accounts()` — writes new format, atomic behavior
- [x] 6.3 Add tests for `UsageWorker` multi-account signal emission — mock API, verify list output
- [x] 6.4 Add tests for dynamic usage row rebuild — verify widget count matches account count, single-account hides name label
