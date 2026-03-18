# Design: wt-web-install-and-docs

## Context

wt-web is a FastAPI dashboard served by uvicorn on port 7400. It has a systemd service template at `templates/systemd/wt-web.service` and an install function in `install.sh`, but no standalone installer and no documentation. Remote access is possible via Tailscale but the setup script has bugs and uses HTTP instead of HTTPS.

## Goals / Non-Goals

**Goals:**
- Standalone `bin/wt-web-install` bash script for service setup
- Interactive Tailscale HTTPS prompt
- Comprehensive `docs/wt-web.md`
- Fix port references in `scripts/setup-tailscale.sh`

**Non-Goals:**
- Replacing `install.sh` (it continues to work, `wt-web-install` is an alternative entry point)
- Custom reverse proxy support

## Decisions

### D1: Bash script in `bin/`, not Python subcommand

`wt-web-install` is a bash script in `bin/` (like other `wt-*` tools) rather than a Python CLI subcommand.

**Rationale:** Systemd and Tailscale operations are shell-native. A bash script avoids Python environment dependencies during installation. Consistent with `bin/wt-new`, `bin/wt-merge`, etc.

### D2: Tailscale HTTPS instead of HTTP

Switch from `--http 80` to `--https 443`. The original HTTP choice was to avoid Certificate Transparency log exposure, but this is not a real security concern — the device must be registered in the tailnet to access the service.

**Rationale:** HTTPS provides end-to-end encryption even within the WireGuard tunnel, and avoids browser mixed-content warnings. CT log visibility of the hostname is acceptable.

### D3: Interactive prompt with flag override

The installer asks interactively about Tailscale, but `--tailscale` flag allows non-interactive use. `--uninstall` is a separate mode.

**Rationale:** Supports both human-interactive and scripted/automated use.

### D4: Reuse existing service template

The installer copies `templates/systemd/wt-web.service` rather than generating inline. Port customization uses `sed` to modify the copied file.

**Rationale:** Single source of truth for the service definition. Changes to the template automatically flow to new installs.

## Risks / Trade-offs

- **[Risk] Tailscale HTTPS cert provisioning requires tailnet HTTPS enabled** → The installer checks `tailscale serve` success and warns if it fails
- **[Risk] Port 7400 conflict** → Health check detects failure and reports

## Open Questions

_(none)_
