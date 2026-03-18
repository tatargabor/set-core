# Tasks: wt-web-install-and-docs

## 1. Bugfix

- [x] 1.1 Fix `scripts/setup-tailscale.sh` port references: change `8765` to `7400` in log messages (lines 87, 91) [REQ: setup-tailscale-bugfix]
- [x] 1.2 Upgrade `scripts/setup-tailscale.sh` from `--http 80` to `--https 443` [REQ: setup-tailscale-bugfix]

## 2. wt-web-install script

- [x] 2.1 Create `bin/wt-web-install` with argument parsing (`--port`, `--tailscale`, `--uninstall`, `--help`) [REQ: service-installation]
- [x] 2.2 Implement service installation: copy template, sed port, systemctl daemon-reload + enable + start [REQ: service-installation]
- [x] 2.3 Implement health check: curl localhost:<port> with retry [REQ: service-installation]
- [x] 2.4 Implement Tailscale HTTPS prompt: detect tailscale, ask user, configure `tailscale serve --https 443` [REQ: tailscale-https-setup-prompt]
- [x] 2.5 Implement `--uninstall`: stop + disable service, remove service file, reset tailscale serve [REQ: service-uninstallation]
- [x] 2.6 Handle existing service detection and template update [REQ: service-installation]
- [x] 2.7 Make script executable, verify it runs without errors [REQ: service-installation]

## 3. Documentation

- [x] 3.1 Create `docs/wt-web.md` with Overview and Quick Start sections [REQ: local-access-documentation]
- [x] 3.2 Add Automated Install section documenting `wt-web-install` usage [REQ: automated-install-documentation]
- [x] 3.3 Add Manual Setup section with systemd and Tailscale step-by-step instructions [REQ: manual-setup-documentation]
- [x] 3.4 Add Configuration section listing environment variables and .env options [REQ: configuration-reference]
- [x] 3.5 Add Troubleshooting section with common issues [REQ: troubleshooting-section]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN user runs `wt-web-install` and no service exists THEN service is installed, enabled, started, and health check passes [REQ: service-installation, scenario: fresh-install]
- [x] AC-2: WHEN user runs `wt-web-install` and service already exists THEN service file is updated if template is newer and service is restarted [REQ: service-installation, scenario: service-already-installed]
- [x] AC-3: WHEN user runs `wt-web-install --port 8000` THEN service listens on port 8000 [REQ: service-installation, scenario: custom-port]
- [x] AC-4: WHEN user accepts Tailscale prompt THEN HTTPS is configured and URL is displayed [REQ: tailscale-https-setup-prompt, scenario: user-accepts-tailscale-setup]
- [x] AC-5: WHEN user declines Tailscale prompt THEN installer completes without Tailscale config [REQ: tailscale-https-setup-prompt, scenario: user-declines-tailscale-setup]
- [x] AC-6: WHEN user runs `wt-web-install --tailscale` THEN Tailscale is configured without prompting [REQ: tailscale-https-setup-prompt, scenario: non-interactive-mode]
- [x] AC-7: WHEN Tailscale is not available THEN installer warns and skips [REQ: tailscale-https-setup-prompt, scenario: tailscale-not-available]
- [x] AC-8: WHEN user runs `wt-web-install --uninstall` THEN service is stopped, disabled, removed, and Tailscale is reset [REQ: service-uninstallation, scenario: uninstall]
- [x] AC-9: WHEN setup-tailscale.sh runs THEN all port references are 7400 [REQ: setup-tailscale-bugfix, scenario: consistent-port-references]
