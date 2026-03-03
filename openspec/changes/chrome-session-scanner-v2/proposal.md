## Why

The v1 Chrome session scanner (from `chrome-session-scanner`) works but has issues discovered during testing: the scan runs synchronously on the main thread (freezing the GUI for ~4s), org-name fetching adds network calls per profile, there's no security review of session key handling, and the `gui/platform` module shadows stdlib `platform` (a pre-existing bug that v1 had to work around). This v2 hardens the implementation for production use.

## What Changes

- Move scan to a background QThread so the GUI never freezes
- Cache org names in `claude-session.json` so subsequent scans are instant (only fetch on first discovery or manual re-scan)
- Remove dead `_load_9router_names()` function
- Fix `gui/platform/__init__.py` stdlib shadowing (move the fix from v1 into a proper, tested solution)
- Add graceful handling for missing `pycookiecheat`: menu button shows install instructions, toolbar button hidden when unavailable

## Capabilities

### New Capabilities
- `background-chrome-scan`: Background thread scanning with progress signals and GUI-safe result delivery

### Modified Capabilities
- `multi-account-usage`: Add org name caching to account storage, handle scan-discovered vs manually-added accounts
- `control-center`: Toolbar button visibility depends on pycookiecheat availability

## Impact

- `gui/workers/chrome_cookies.py` — refactor to background worker pattern
- `gui/control_center/mixins/handlers.py` — async scan handlers
- `gui/control_center/main_window.py` — conditional toolbar button
- `gui/platform/__init__.py` — stdlib platform fix
- `tests/gui/test_17_chrome_cookies.py` — update tests
- `~/.config/wt-tools/claude-session.json` — org name caching in account entries
