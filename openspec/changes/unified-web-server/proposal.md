# Unified Web Server

## Why

The set-web production server (`set-orch-core serve` on port 7400) serves the built SPA and API. The new set-manager runs on port 3112. When accessing set-web remotely (e.g., via Tailscale), only port 7400 is reachable — the manager API on 3112 is inaccessible. This means the `/manager` pages can't fetch data.

## What Changes

- Add reverse proxy in `server.py`: `/api/manager/*` requests are forwarded to `localhost:3112`
- Single port (7400) serves everything: SPA, set-orch API, and manager API
- No new dependencies (use httpx or aiohttp for async proxying, or simple urllib)

## Capabilities

### New Capabilities
- `manager-proxy`: Reverse proxy from set-web to set-manager API

## Impact

- `lib/set_orch/server.py` — add proxy route
