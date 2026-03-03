## 1. Cleanup and Dead Code Removal

- [x] 1.1 Remove `_load_9router_names()` function from `gui/workers/chrome_cookies.py`

## 2. Background Worker

- [x] 2.1 Create `ChromeScanWorker(QThread)` class in `gui/workers/chrome_cookies.py` with `scan_finished(list)` and `scan_error(str)` signals
- [x] 2.2 Add `force_refresh` parameter to `scan_chrome_sessions()` to control whether org names are re-fetched or use cache
- [x] 2.3 Add org name caching logic: load existing accounts, skip `_fetch_org_name()` when cached org_name exists and sessionKey unchanged (unless `force_refresh=True`)

## 3. Account Metadata

- [x] 3.1 Add `source` field to accounts saved by Chrome scanner (`"chrome-scan"`) and Add Account dialog (`"manual"`)
- [x] 3.2 Implement merge logic in scanner save: preserve `manual` accounts, update/add `chrome-scan` accounts

## 4. GUI Integration

- [x] 4.1 Refactor `_auto_scan_chrome()` in handlers.py to use `ChromeScanWorker` instead of calling `scan_chrome_sessions()` directly
- [x] 4.2 Refactor `on_scan_chrome_sessions()` in handlers.py to use `ChromeScanWorker` with `force_refresh=True`, show result dialog on signal
- [x] 4.3 Add concurrent scan prevention: check `isRunning()` before starting a new worker
- [x] 4.4 Hide toolbar scan button (`btn_scan`) when `is_pycookiecheat_available()` returns False in `main_window.py`

## 5. Tests

- [x] 5.1 Add test for `ChromeScanWorker` signal emission (mock `scan_chrome_sessions`, verify `scan_finished` signal)
- [x] 5.2 Add test for org name caching: verify `_fetch_org_name` is skipped when cache is valid
- [x] 5.3 Add test for stdlib `platform` module fix: verify `import platform; platform.system()` works after `import gui.platform`
- [x] 5.4 Update existing tests in `test_17_chrome_cookies.py` for new `force_refresh` parameter
