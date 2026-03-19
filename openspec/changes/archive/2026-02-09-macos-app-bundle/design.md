## Context

On macOS, application launchers (Spotlight, Alfred, Raycast) only discover `.app` bundles — not shell scripts. The existing `wt-control` shell wrapper in `~/.local/bin/` works perfectly from the terminal but is invisible to these launchers. Linux already has a `.desktop` entry for Alt+F2 discovery. macOS needs the equivalent.

A macOS `.app` bundle is just a directory with a specific structure:

```
WT Control.app/
  Contents/
    Info.plist          ← XML metadata (name, identifier, icon)
    MacOS/
      wt-control        ← executable (shell script wrapper)
    Resources/
      app.icns          ← icon (optional)
```

The existing `bin/wt-control` shell script already handles all the hard parts: symlink resolution, PYTHONPATH setup, Python discovery, PySide6 auto-install, and error logging. The `.app` wrapper just needs to call it.

## Goals / Non-Goals

**Goals:**
- `wt-control` discoverable via Cmd+Space (Spotlight), Alfred, Raycast
- Pinnable to the Dock
- Generated automatically by `install.sh` (macOS only)
- Zero manual steps after install
- Delegates to existing `wt-control` wrapper — no duplicated logic

**Non-Goals:**
- Code signing or notarization (not needed for local-only apps)
- DMG/pkg distribution (users install via git clone + install.sh)
- Custom app icon design (use a generic terminal icon; `.icns` slot is there for later)
- Gatekeeper bypass (local apps in ~/Applications aren't subject to this)

## Decisions

### 1. Install location: `~/Applications/` (not `/Applications/`)

`~/Applications/` is the per-user applications folder. Spotlight indexes it by default. No `sudo` required. This matches the install philosophy (everything in user space, no root needed).

Alternative considered: `/Applications/` — requires sudo, inappropriate for a dev tool installed from source.

### 2. Bundle executable: thin wrapper calling `~/.local/bin/wt-control`

The `.app` bundle's `MacOS/wt-control` script will be a 3-line wrapper:

```bash
#!/bin/bash
exec "$HOME/.local/bin/wt-control" "$@"
```

This keeps all logic in `bin/wt-control` (symlink resolution, PYTHONPATH, Python discovery). The `.app` is just a launcher facade.

Alternative considered: Copying the full `bin/wt-control` logic into the `.app` — rejected because it would create a second copy to maintain. Also, the symlink resolution in `bin/wt-control` already handles finding the project root.

### 3. `Info.plist`: minimal, hardcoded XML

Generate `Info.plist` inline in `install.sh` using a heredoc. Fields:
- `CFBundleName`: "WT Control"
- `CFBundleIdentifier`: "com.set-core.control"
- `CFBundleExecutable`: "wt-control"
- `CFBundleIconFile`: "app" (references `app.icns` if present)
- `LSUIElement`: true (hides from Dock by default — the app lives in the system tray)

`LSUIElement=true` is important: PySide6 apps using `setQuitOnLastWindowClosed(False)` with a tray icon should not show a persistent Dock icon. Users can still pin it manually.

Alternative considered: `LSUIElement=false` (always show in Dock) — rejected because the Control Center is a tray app that intentionally runs in the background.

### 4. App icon: optional placeholder

Ship no icon initially. The `Info.plist` references `app.icns`, but if the file doesn't exist macOS shows a generic app icon. This is fine for now. An icon can be added later by placing `app.icns` in `Resources/`.

### 5. Integrate into existing `install.sh` flow

Add a new function `install_macos_app_bundle()` called from `main()` with a platform guard (`[[ "$OSTYPE" == darwin* ]]`). Place it alongside `install_desktop_entry()` — the macOS equivalent.

## Risks / Trade-offs

- **Spotlight indexing delay** → After first install, Spotlight may take a few seconds to index `~/Applications/`. The install script can trigger `mdimport ~/Applications/WT\ Control.app` to speed it up.
- **Stale wrapper after uninstall** → If user removes set-core but leaves the `.app`, launching it will fail. Mitigation: the wrapper script will show a clear error if `wt-control` is not found.
- **LSUIElement hides Dock icon** → Users expecting a Dock icon won't see one by default. This is intentional for a tray app, but worth documenting.

## Open Questions

None — the approach is straightforward.
