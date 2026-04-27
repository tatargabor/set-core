# Web Service Lifecycle Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: CLI serve subcommand
`set-orch-core serve` SHALL start the FastAPI server with uvicorn. It SHALL accept `--port` (default 7400) and `--host` (default 127.0.0.1) flags. It SHALL serve both the API endpoints and the built SPA static files.

#### Scenario: Default start
- **WHEN** user runs `set-orch-core serve`
- **THEN** the server starts on `127.0.0.1:7400` and logs "set-web dashboard running at http://localhost:7400"

#### Scenario: Custom port
- **WHEN** user runs `set-orch-core serve --port 8080`
- **THEN** the server starts on port 8080

#### Scenario: Port in use
- **WHEN** port 7400 is already in use
- **THEN** the server logs a clear error message and exits with code 1

### Requirement: Environment variable configuration
The server SHALL read `WT_WEB_PORT` environment variable as an alternative to `--port`. CLI flag takes precedence over environment variable.

#### Scenario: Env var port
- **WHEN** `WT_WEB_PORT=9000` is set and no `--port` flag is given
- **THEN** the server starts on port 9000

### Requirement: systemd user service
A systemd user service file SHALL be provided that runs `set-orch-core serve` as an always-on background service with auto-restart on failure.

#### Scenario: Service auto-start
- **WHEN** user logs in to their desktop session
- **THEN** the set-web service starts automatically and `localhost:7400` becomes available

#### Scenario: Service crash recovery
- **WHEN** the server process crashes
- **THEN** systemd restarts it within 5 seconds

#### Scenario: Service status check
- **WHEN** user runs `systemctl --user status set-web`
- **THEN** the service status, PID, and recent log lines are displayed

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

### Requirement: install.sh integration
The install script (`install.sh`) SHALL detect the platform and install the appropriate service manager integration — systemd on Linux, launchd on macOS. It SHALL resolve `__SET_TOOLS_ROOT__` dynamically and enable the service on first install.

#### Scenario: Service install on Linux
- **WHEN** install.sh runs on a Linux system with systemd
- **THEN** the systemd user service is installed and enabled (existing behavior)

#### Scenario: Service install on macOS
- **WHEN** install.sh runs on macOS
- **THEN** the launchd user agent plist is installed to `~/Library/LaunchAgents/` and loaded

#### Scenario: Fresh install
- **WHEN** `install.sh` runs and no set-web service exists
- **THEN** the service file is copied to the appropriate location, and the service is enabled and started

#### Scenario: Update install
- **WHEN** `install.sh` runs and the service file has changed
- **THEN** the old service is stopped, the file is updated, and the service is restarted

### Requirement: Graceful shutdown
The server SHALL handle SIGTERM gracefully: close all WebSocket connections, stop file watchers, then exit.

#### Scenario: SIGTERM signal
- **WHEN** the server receives SIGTERM (systemd stop)
- **THEN** all WebSocket clients receive a close frame, file watchers are stopped, and the process exits within 5 seconds

### Requirement: SPA build integration
The web SPA SHALL be buildable via `npm run build` in the `web/` directory. The build output (`web/dist/`) SHALL be committed to git so that users without Node.js can run the server with the pre-built frontend.

#### Scenario: Build and serve
- **WHEN** `npm run build` completes in `web/`
- **THEN** `web/dist/` contains `index.html` and asset bundles that FastAPI can serve

#### Scenario: No Node.js installed
- **WHEN** a user installs set-core without Node.js
- **THEN** the server serves the pre-built `web/dist/` from the git repository
