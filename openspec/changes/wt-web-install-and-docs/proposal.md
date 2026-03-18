# Proposal: wt-web-install-and-docs

## Why

The wt-web dashboard has no standalone installation command and no documentation. Users must read `install.sh` source code to understand how to set up the service. Remote access via Tailscale HTTPS is undocumented and the existing setup script contains port reference bugs (references `8765` instead of `7400`).

## What Changes

- **New**: `bin/wt-web-install` — standalone interactive installer for the wt-web systemd service with optional Tailscale HTTPS setup
- **New**: `docs/wt-web.md` — comprehensive documentation covering local access, remote access, automated and manual setup
- **Fix**: `scripts/setup-tailscale.sh` — correct stale port references (`8765` → `7400`), upgrade from HTTP :80 to HTTPS :443
- **Enhancement**: Tailscale setup moves from HTTP-only to HTTPS (the CT log concern is not a security risk since device must be registered in the tailnet)

## Capabilities

### New Capabilities
- `wt-web-install` — standalone service installer CLI tool
- `wt-web-docs` — wt-web dashboard documentation

### Modified Capabilities
_(none — no existing specs affected)_

## Impact

- `bin/wt-web-install` — new executable, added to PATH via install.sh
- `scripts/setup-tailscale.sh` — bugfix + HTTP→HTTPS upgrade
- `docs/wt-web.md` — new documentation file
- `templates/systemd/wt-web.service` — may need review for consistency with installer
