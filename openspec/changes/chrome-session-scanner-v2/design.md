## Context

The v1 Chrome session scanner works end-to-end: it discovers Chrome profiles, extracts `sessionKey` cookies via pycookiecheat, fetches org names from the Claude API, and saves accounts to `claude-session.json`. However, v1 has production-readiness issues:

1. **Main-thread blocking**: `scan_chrome_sessions()` runs synchronously on the GUI thread. Keyring access + cookie decryption + N API calls takes ~4s, freezing the UI.
2. **Redundant network calls**: Every scan re-fetches org names from `claude.ai/api/organizations` for each profile, even when sessions haven't changed.
3. **Dead code**: `_load_9router_names()` is unused.
4. **stdlib shadowing**: `gui/platform/__init__.py` shadows stdlib `platform`, breaking third-party imports. The v1 workaround (injecting into `sys.modules`) works but needs a proper test.
5. **Missing graceful degradation**: When pycookiecheat isn't installed, the toolbar scan button still shows with no indication of what's wrong.

Current flow:
```
GUI startup → QTimer.singleShot(2s) → _auto_scan_chrome() [main thread]
  → scan_chrome_sessions()
    → _get_chrome_password()     [keyring access, ~0.5s]
    → for each profile:
      → _extract_session_cookie() [cookie decrypt, ~0.5s each]
      → _fetch_org_name()         [HTTP call, ~1s each]
    → deduplicate by name
  → save_accounts()
  → _restart_usage_worker()
```

## Goals / Non-Goals

**Goals:**
- Move Chrome scanning to a background QThread so the GUI never freezes
- Cache org names in account entries so repeat scans skip the API call
- Remove dead `_load_9router_names()` function
- Add a test for the stdlib `platform` module fix in `gui/platform/__init__.py`
- Show install instructions when pycookiecheat is missing; hide toolbar button when unavailable

**Non-Goals:**
- Supporting browsers other than Chrome (Brave, Firefox, etc.)
- Encrypting session keys at rest (they're already equivalent to browser cookies on disk)
- Adding a progress bar or cancel button (scan completes in <2s when cached)

## Decisions

### D1: QThread worker pattern for background scanning

**Choice**: Create a `ChromeScanWorker(QThread)` class that emits results via Qt signals.

**Rationale**: The codebase already uses this pattern for `StatusWorker`, `UsageWorker`, `TeamWorker`, etc. in `gui/workers/`. A QThread with signals integrates naturally with the existing `_auto_scan_chrome()` and `on_scan_chrome_sessions()` handlers.

**Alternative considered**: `QRunnable` + `QThreadPool` — rejected because we need signals for progress/result delivery, and QRunnable requires a separate QObject for signals (more boilerplate for no benefit).

**Design**:
```
ChromeScanWorker(QThread)
  signals:
    scan_finished(list)   # [{name, sessionKey, org_name}, ...]
    scan_error(str)       # error message
  run():
    results = scan_chrome_sessions()
    self.scan_finished.emit(results)
```

The handlers in `HandlersMixin` will:
- `_auto_scan_chrome()`: Create worker, connect signals, start (silent — no dialog)
- `on_scan_chrome_sessions()`: Create worker, connect signals, start (show result dialog on finish)

### D2: Org name caching in claude-session.json

**Choice**: Store `org_name` alongside `sessionKey` in each account entry. On scan, skip the API call if `org_name` is already present and `sessionKey` hasn't changed.

**Rationale**: The org name rarely changes. Caching it eliminates N HTTP calls per scan (the slowest part). Manual re-scan (`on_scan_chrome_sessions`) always re-fetches to pick up changes.

**Format**:
```json
{
  "accounts": [
    {"name": "tg", "sessionKey": "sk-ant-...", "org_name": "tg", "source": "chrome-scan"},
    {"name": "Work", "sessionKey": "sk-ant-...", "source": "manual"}
  ]
}
```

- `source: "chrome-scan"` — added by scanner, org name cached
- `source: "manual"` — added by user via Add Account dialog, no org name cache
- Auto-scan merges: updates sessionKey for existing `chrome-scan` accounts, preserves `manual` accounts

### D3: Toolbar button conditional visibility

**Choice**: Check `is_pycookiecheat_available()` at window init time. If unavailable, hide the toolbar scan button. The menu action remains but shows install instructions when clicked.

**Rationale**: A hidden button avoids confusion. The menu action stays discoverable so users know the feature exists and how to enable it.

### D4: Remove dead code

**Choice**: Delete `_load_9router_names()` entirely.

**Rationale**: It was a spike that's never called. The org name approach via Claude API is the production solution.

### D5: Platform module test

**Choice**: Add a test in `test_17_chrome_cookies.py` that verifies `import platform; platform.system()` works after `gui.platform` has been imported.

**Rationale**: This is a regression test for the stdlib shadowing fix. It should catch any future changes to `gui/platform/__init__.py` that break the workaround.

## Risks / Trade-offs

- **[Stale org name cache]** → Mitigated by always re-fetching on manual scan. Auto-scan uses cache. Users can re-scan from the menu.
- **[QThread lifecycle]** → Worker must be kept alive (stored as instance attribute) until signals fire. If the window closes mid-scan, the thread should be stopped gracefully. Mitigated by checking `isRunning()` before starting a new scan.
- **[pycookiecheat import cost]** → The `is_pycookiecheat_available()` check imports the module. This is fine at startup (already done in v1) but should not be called repeatedly. Cache the result.
