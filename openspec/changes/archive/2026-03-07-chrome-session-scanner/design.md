## Context

The wt-control GUI currently requires manual session key entry via F12 → DevTools → Cookies. This is stored in `~/.config/set-core/claude-session.json` as a list of `{name, sessionKey}` dicts. The `UsageWorker` polls the Claude API every 30s using these session keys. Chrome stores cookies in per-profile SQLite databases with AES-256-GCM encryption (v11 prefix), keys stored in the OS keyring (gnome-keyring on Linux, Keychain on macOS).

## Goals / Non-Goals

**Goals:**
- Zero-friction account setup: scan all Chrome profiles, extract session cookies, populate the account list automatically
- One-click rescan via toolbar button and menu item
- Auto-scan on startup so accounts are always current
- Show user-friendly profile names (from Chrome's Preferences file)

**Non-Goals:**
- Supporting Chromium, Brave, Edge, or Firefox (Chrome only for now)
- Encrypting session keys at rest in `claude-session.json` (they're already ephemeral cookies)
- Background periodic rescanning (manual trigger or startup only)
- Windows support (Linux and macOS via `pycookiecheat`)

## Decisions

### D1: Use `pycookiecheat` for cookie decryption

**Decision**: Use the `pycookiecheat` library rather than implementing raw decryption.

**Alternatives considered**:
- Raw `secretstorage` + `pycryptodome`: More control but reimplements what `pycookiecheat` already does, two extra dependencies instead of one
- `secret-tool lookup` subprocess + manual AES: No Python deps but fragile subprocess parsing and custom crypto code

**Rationale**: `pycookiecheat` is a maintained, single-purpose library that handles Chrome's evolving encryption scheme across platforms. It abstracts OS keyring access and AES-GCM decryption into a single call.

### D2: Profile name resolution from Preferences JSON

**Decision**: Read `~/.config/google-chrome/<Profile>/Preferences` and extract:
1. `account_info[0].full_name` (Google account name) — primary
2. `profile.name` (Chrome profile display name) — fallback
3. Directory name (e.g. "Profile 1") — last resort

**Rationale**: The Google account name is the most recognizable identifier for users. The Chrome profile name is a good fallback when no Google account is signed in.

### D3: Full replace on scan

**Decision**: Each scan replaces the entire `claude-session.json` accounts list with freshly discovered sessions.

**Rationale**: Session cookies rotate. Stale entries cause API failures that show as `--` in the usage bars. A full replace ensures the list always reflects reality. Users who need manual accounts (non-Chrome) can use "Add Account..." after scanning — but this is an edge case we accept losing on rescan.

### D4: Scanner module as a standalone utility

**Decision**: Create `gui/workers/chrome_cookies.py` with a pure function `scan_chrome_sessions() -> list[dict]` that returns `[{"name": str, "sessionKey": str}]`. The GUI calls this synchronously (it's fast — SQLite reads + JSON parsing).

**Rationale**: Keeping the scanner as a pure function makes it testable independently of the GUI. The scan operation is fast (< 1s) so no need for a background QThread.

### D5: Toolbar button placement

**Decision**: Place a `🔍` button in the bottom button bar, between the active filter button and the minimize button.

**Rationale**: Keeps it accessible alongside other utility buttons. The hamburger menu also has the action for discoverability.

## Risks / Trade-offs

- **[Risk] Chrome locks cookie DB while running** → `pycookiecheat` copies the DB to a temp file before reading, avoiding lock conflicts
- **[Risk] `pycookiecheat` not installed** → Graceful degradation: show a warning dialog with install instructions (`pip install pycookiecheat`), fall back to manual entry
- **[Risk] No Chrome profiles found** → Show informational dialog "No Chrome profiles with Claude sessions found"
- **[Risk] Scan replaces manually added accounts** → Acceptable trade-off; manual accounts are rare and can be re-added. Could be improved later with a "pinned" flag
- **[Risk] Profile detection fails on non-standard Chrome installations** → Use platform-specific default paths, don't attempt to discover custom installations
