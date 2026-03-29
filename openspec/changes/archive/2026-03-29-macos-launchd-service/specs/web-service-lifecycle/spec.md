## ADDED Requirements

### Requirement: macOS launchd user service
A launchd user agent plist SHALL be provided at `templates/launchd/com.set-core.web.plist` that runs `set-orch-core serve` as an always-on background service with auto-restart on failure. The plist SHALL use `KeepAlive: true` and set PYTHONPATH and PATH dynamically based on the set-core install location.

#### Scenario: Service auto-start on login
- **WHEN** user logs in to their macOS session and the plist is loaded
- **THEN** the set-web service starts automatically and `localhost:7400` becomes available

#### Scenario: Service crash recovery
- **WHEN** the server process crashes on macOS
- **THEN** launchd restarts it automatically

#### Scenario: Service status check
- **WHEN** user runs `launchctl list | grep set-core`
- **THEN** the service PID and status are displayed

### Requirement: launchd plist dynamic PYTHONPATH
The plist template SHALL contain placeholder tokens (`__SET_TOOLS_ROOT__`) that `install.sh` resolves at install time, matching the pattern used by the systemd service template.

#### Scenario: PYTHONPATH resolution
- **WHEN** install.sh installs the plist
- **THEN** `__SET_TOOLS_ROOT__` is replaced with the actual set-core directory path in the installed plist

### Requirement: install.sh launchd integration
`install.sh` SHALL detect macOS and install the launchd plist to `~/Library/LaunchAgents/`. It SHALL use `launchctl load` to activate the service and `launchctl unload` to deactivate any previous version first.

#### Scenario: Fresh macOS install
- **WHEN** install.sh runs on macOS with no existing plist
- **THEN** the plist is copied to `~/Library/LaunchAgents/com.set-core.web.plist`, loaded, and the service starts

#### Scenario: Re-install on macOS
- **WHEN** install.sh runs on macOS with an existing plist loaded
- **THEN** the old plist is unloaded, replaced with the new version, and reloaded

#### Scenario: Platform dispatch
- **WHEN** install.sh runs on Linux
- **THEN** systemd service install runs (existing behavior, unchanged)

## MODIFIED Requirements

### Requirement: install.sh integration
The install script (`install.sh`) SHALL detect the platform and install the appropriate service manager integration — systemd on Linux, launchd on macOS. It SHALL resolve `__SET_TOOLS_ROOT__` dynamically and enable the service on first install.

#### Scenario: Service install on Linux
- **WHEN** install.sh runs on a Linux system with systemd
- **THEN** the systemd user service is installed and enabled (existing behavior)

#### Scenario: Service install on macOS
- **WHEN** install.sh runs on macOS
- **THEN** the launchd user agent plist is installed to `~/Library/LaunchAgents/` and loaded
