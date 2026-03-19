## Why

Adding Claude accounts to wt-control currently requires manually opening browser DevTools (F12 → Application → Cookies → claude.ai → sessionKey) and pasting the session key. This is tedious, error-prone, and must be repeated for each Chrome profile. Users with multiple Chrome profiles (personal, work, etc.) need to do this N times and keep track of which account is which.

Chrome stores all the data needed — session cookies and profile names — in well-known locations. Automating this extraction eliminates friction and ensures all accounts are always up to date.

## What Changes

- Add a Chrome session scanner that discovers all Chrome profiles, reads profile names, and extracts `sessionKey` cookies from each profile's cookie database
- Add a toolbar button (`🔍`) to trigger the scan on demand
- Add a menu item "Scan Chrome Sessions" in the main hamburger menu
- Auto-scan on application startup (after a short delay) to populate accounts without any user action
- When scanning, replace the entire account list in `claude-session.json` with freshly discovered sessions
- Use `pycookiecheat` library for cookie decryption (handles Chrome's v11 AES-256-GCM encryption via OS keyring)

## Capabilities

### New Capabilities
- `chrome-session-scanner`: Automatic discovery and extraction of Claude session cookies from all local Chrome profiles, with profile name resolution and integration into the existing multi-account usage system

### Modified Capabilities
- `multi-account-usage`: Add auto-population of accounts via Chrome scan (replaces manual-only entry), add toolbar scan button, add autorun-on-startup behavior

## Impact

- **New dependency**: `pycookiecheat` Python package (handles Chrome cookie decryption on Linux/macOS/Windows)
- **GUI changes**: New toolbar button in button bar, new menu item in hamburger menu
- **Files affected**: `gui/control_center/main_window.py` (toolbar button, autorun timer), `gui/control_center/mixins/menus.py` (menu item), `gui/control_center/mixins/handlers.py` (scan handler), new `gui/workers/chrome_cookies.py` (scanner logic)
- **Config**: `~/.config/set-core/claude-session.json` accounts list will be overwritten on each scan
- **Platform**: Linux primary (Chrome at `~/.config/google-chrome/`), macOS support via `pycookiecheat` (Chrome at `~/Library/Application Support/Google/Chrome/`)
