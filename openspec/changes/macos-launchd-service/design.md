# Design: macOS launchd Service

## Context

Linux uses systemd user services (`~/.config/systemd/user/set-web.service`). macOS uses launchd with property list files in `~/Library/LaunchAgents/`. The existing systemd template uses `__SET_TOOLS_ROOT__` placeholder for PYTHONPATH resolution at install time.

## Goals / Non-Goals

**Goals:**
- Parity with Linux: auto-start at login, auto-restart on crash
- Same `__SET_TOOLS_ROOT__` placeholder pattern for consistency
- Clean upgrade path (unload old, load new)

**Non-Goals:**
- System-wide daemon (we only need user-level agent)
- launchd socket activation (not needed for always-on server)

## Decisions

### 1. Plist location: `~/Library/LaunchAgents/`
User agents in `~/Library/LaunchAgents/` auto-load on login. No sudo needed.
Alternative: `/Library/LaunchDaemons/` — rejected, requires root and runs as system daemon.

### 2. Service label: `com.set-core.web`
Follows reverse-DNS convention. Matches the plist filename.

### 3. PYTHONPATH in EnvironmentVariables
launchd plist uses `<key>EnvironmentVariables</key>` dict. We set PYTHONPATH and PATH here, resolved from `__SET_TOOLS_ROOT__` at install time — same as the systemd template.

### 4. Unload-before-load pattern
`launchctl unload` then `launchctl load` ensures clean upgrade. `launchctl bootout`/`bootstrap` is the modern API but `load`/`unload` works on all supported macOS versions.

### 5. Rename `install_web_service()` to platform dispatcher
Current function is Linux-only. Make it detect platform and call `install_launchd_service()` on macOS, keeping existing `install_systemd_service()` logic for Linux.

## Risks / Trade-offs

- [Risk] `launchctl load` is deprecated in newer macOS in favor of `launchctl bootstrap` → Mitigation: use `load`/`unload` which still works on all current macOS versions; add TODO for future migration
- [Risk] PYTHONPATH may need brew paths on macOS → Mitigation: include `/opt/homebrew/lib/python3.*/site-packages` in PATH resolution at install time
