# Spec: wt-web-install

## ADDED Requirements

## IN SCOPE
- Interactive systemd service installation for wt-web
- Optional Tailscale HTTPS remote access setup
- Service uninstallation
- Health check after install
- Port reference bugfix in setup-tailscale.sh

## OUT OF SCOPE
- Tailscale installation (handled by existing setup-tailscale.sh)
- Web frontend build (assumes `web/dist/` already exists)
- Custom reverse proxy configurations (nginx, caddy)

### Requirement: Service installation

The `wt-web-install` command SHALL install the wt-web systemd user service, enable it, start it, and verify it is running.

#### Scenario: Fresh install
- **WHEN** user runs `wt-web-install` and no service exists
- **THEN** the service template is copied to `~/.config/systemd/user/wt-web.service`, daemon is reloaded, service is enabled and started, and a health check confirms `localhost:<port>` responds

#### Scenario: Service already installed
- **WHEN** user runs `wt-web-install` and the service file already exists
- **THEN** the installer detects the existing service, updates the service file if the template is newer, and restarts the service

#### Scenario: Custom port
- **WHEN** user runs `wt-web-install --port 8000`
- **THEN** the service is configured to listen on port 8000 instead of the default 7400

### Requirement: Tailscale HTTPS setup prompt

After service installation, the installer SHALL ask the user if they want to enable Tailscale HTTPS remote access.

#### Scenario: User accepts Tailscale setup
- **WHEN** service is installed and user answers yes to the Tailscale prompt
- **THEN** the installer configures `tailscale serve --https 443` pointing to the local wt-web port and displays the resulting HTTPS URL

#### Scenario: User declines Tailscale setup
- **WHEN** user answers no to the Tailscale prompt
- **THEN** the installer skips Tailscale configuration and completes

#### Scenario: Non-interactive mode
- **WHEN** user runs `wt-web-install --tailscale`
- **THEN** Tailscale HTTPS is configured without prompting

#### Scenario: Tailscale not available
- **WHEN** Tailscale is not installed or not connected
- **THEN** the installer warns that Tailscale is unavailable and skips remote access setup

### Requirement: Service uninstallation

The installer SHALL support removing the wt-web service.

#### Scenario: Uninstall
- **WHEN** user runs `wt-web-install --uninstall`
- **THEN** the service is stopped, disabled, the service file is removed, and Tailscale serve is reset if it was configured

### Requirement: Setup-tailscale bugfix

The `scripts/setup-tailscale.sh` SHALL reference the correct default port (7400) in all log messages and error hints.

#### Scenario: Consistent port references
- **WHEN** the script runs or displays help text
- **THEN** all port references use 7400, not 8765
