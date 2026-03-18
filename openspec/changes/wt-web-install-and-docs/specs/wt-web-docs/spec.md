# Spec: wt-web-docs

## ADDED Requirements

## IN SCOPE
- Documentation for wt-web dashboard access (local and remote)
- Automated install instructions (wt-web-install)
- Manual setup instructions (systemd, Tailscale)
- Configuration reference (.env, environment variables)
- Troubleshooting section

## OUT OF SCOPE
- API endpoint reference (belongs in separate API docs)
- Frontend development guide
- Architecture documentation

### Requirement: Local access documentation

The documentation SHALL explain how to access wt-web locally via `localhost:7400`.

#### Scenario: Quick start
- **WHEN** a user reads the quick start section
- **THEN** they understand how to start wt-web and access it in a browser

### Requirement: Automated install documentation

The documentation SHALL cover the `wt-web-install` command with all flags and interactive prompts.

#### Scenario: Install command reference
- **WHEN** a user reads the automated install section
- **THEN** they understand all available flags (`--port`, `--tailscale`, `--uninstall`) and the interactive flow

### Requirement: Manual setup documentation

The documentation SHALL provide step-by-step manual instructions for both systemd service setup and Tailscale HTTPS configuration.

#### Scenario: Manual systemd setup
- **WHEN** a user follows the manual systemd instructions
- **THEN** they can copy the service file, reload systemd, enable and start the service

#### Scenario: Manual Tailscale HTTPS setup
- **WHEN** a user follows the manual Tailscale instructions
- **THEN** they can configure `tailscale serve --https 443` and access wt-web from a remote device on the tailnet

### Requirement: Configuration reference

The documentation SHALL list all environment variables and `.env` options that affect wt-web.

#### Scenario: Environment variable reference
- **WHEN** a user reads the configuration section
- **THEN** they find `WT_WEB_PORT`, `WT_TAILSCALE_HOSTNAME`, and other relevant variables with descriptions and defaults

### Requirement: Troubleshooting section

The documentation SHALL include common issues and solutions.

#### Scenario: Service won't start
- **WHEN** a user encounters a service startup failure
- **THEN** they find diagnostic steps (journalctl, port conflicts, Python path issues)
