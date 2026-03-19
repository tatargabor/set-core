## ADDED Requirements

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

### Requirement: install.sh integration
The `install.sh` script SHALL deploy the systemd service file and enable it. It SHALL handle both fresh install and update scenarios.

#### Scenario: Fresh install
- **WHEN** `install.sh` runs and no set-web service exists
- **THEN** the service file is copied to `~/.config/systemd/user/`, `daemon-reload` is run, and the service is enabled and started

#### Scenario: Update install
- **WHEN** `install.sh` runs and the service file has changed
- **THEN** the service file is updated, `daemon-reload` is run, and the service is restarted

#### Scenario: No systemd
- **WHEN** the system does not have systemd (macOS, minimal containers)
- **THEN** `install.sh` skips service deployment and prints instructions for manual startup

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
