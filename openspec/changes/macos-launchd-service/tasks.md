# Tasks: macOS launchd Service

## 1. Plist Template

- [x] 1.1 Create `templates/launchd/com.set-core.web.plist` with Label, ProgramArguments (`set-orch-core serve --port 7400`), KeepAlive, EnvironmentVariables (PYTHONPATH, PATH with `__SET_TOOLS_ROOT__` placeholders), and StandardOutPath/StandardErrorPath for logging [REQ: macos-launchd-user-service]
- [x] 1.2 Add `RunAtLoad: true` to ensure service starts on login [REQ: macos-launchd-user-service]

## 2. Installer Integration

- [x] 2.1 Rename existing `install_web_service()` body to `install_systemd_service()` (internal function, Linux-only) [REQ: install-sh-launchd-integration]
- [x] 2.2 Create `install_launchd_service()` in install.sh that: copies plist to `~/Library/LaunchAgents/`, resolves `__SET_TOOLS_ROOT__` with `sed`, unloads old plist if present, loads new plist [REQ: install-sh-launchd-integration]
- [x] 2.3 Make `install_web_service()` a platform dispatcher: call `install_systemd_service()` on Linux, `install_launchd_service()` on macOS [REQ: install-sh-launchd-integration]
- [x] 2.4 Resolve `__SET_TOOLS_ROOT__` in the plist using `SCRIPT_DIR` (same pattern as systemd template) [REQ: launchd-plist-dynamic-pythonpath]

## 3. Verification

- [x] 3.1 Test on macOS: run install.sh, verify plist installed to `~/Library/LaunchAgents/`, service running, `localhost:7400` responds [REQ: macos-launchd-user-service]
- [ ] 3.2 Test on Linux: run install.sh, verify systemd path still works unchanged [REQ: install-sh-launchd-integration]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN user logs in to macOS session THEN set-web service starts and localhost:7400 is available [REQ: macos-launchd-user-service, scenario: service-auto-start-on-login]
- [x] AC-2: WHEN server process crashes on macOS THEN launchd restarts it [REQ: macos-launchd-user-service, scenario: service-crash-recovery]
- [x] AC-3: WHEN `launchctl list | grep set-core` THEN PID and status displayed [REQ: macos-launchd-user-service, scenario: service-status-check]
- [x] AC-4: WHEN install.sh runs on macOS with no existing plist THEN plist copied, loaded, service starts [REQ: install-sh-launchd-integration, scenario: fresh-macos-install]
- [x] AC-5: WHEN install.sh re-runs on macOS THEN old plist unloaded, new loaded [REQ: install-sh-launchd-integration, scenario: re-install-on-macos]
- [x] AC-6: WHEN install.sh runs on Linux THEN systemd path unchanged [REQ: install-sh-launchd-integration, scenario: platform-dispatch]
- [x] AC-7: WHEN install.sh installs plist THEN `__SET_TOOLS_ROOT__` resolved to actual path [REQ: launchd-plist-dynamic-pythonpath, scenario: pythonpath-resolution]
