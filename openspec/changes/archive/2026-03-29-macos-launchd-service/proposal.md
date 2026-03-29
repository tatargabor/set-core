# Proposal: macOS launchd Service

## Why

set-core's `set-web` dashboard service only has a systemd user service for Linux. On macOS there is no automated way to start `set-orch-core serve` at login — users must run it manually every time. macOS uses launchd instead of systemd, so a `.plist` template and installer integration are needed.

## What Changes

- **Add launchd plist template** — `templates/launchd/com.set-core.web.plist` mirroring the systemd service behavior (auto-start, restart on crash, correct PYTHONPATH/PATH)
- **Add `install_launchd_service()` to install.sh** — macOS counterpart to `install_web_service()` that installs the plist, loads it via `launchctl`, and resolves PYTHONPATH dynamically
- **Platform-aware service install** — `install_web_service()` dispatches to systemd on Linux, launchd on macOS

## Capabilities

### Modified Capabilities

- `web-service-lifecycle` — adding macOS launchd requirements alongside existing systemd requirements

## Impact

- **install.sh**: new `install_launchd_service()` function, `install_web_service()` becomes platform dispatcher
- **templates/**: new `launchd/com.set-core.web.plist` template file
- **No API changes** — the server itself is unchanged, only the service management layer
