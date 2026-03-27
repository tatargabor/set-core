# Proposal: Unified Web Service

## Why

set-core currently runs two separate services (set-orch-core on port 7400, set-manager on port 3112) with different web frameworks (FastAPI vs aiohttp), separate project registries (projects.json vs runtime dict), and overlapping API routes. The browser doesn't know which port to hit, Tailscale proxy breaks, and projects registered in one service don't appear in the other. The orchestration engine, sentinel, and issue management form a single coherent system that should be served from a single API.

## What Changes

- **Merge manager API routes into FastAPI** — port aiohttp routes (sentinel, issues, mutes, groups) to FastAPI routers
- **Split api.py into domain modules** — break the monolithic 2300-line api.py into focused modules under `lib/set_orch/api/`
- **Unified project registry** — both services read from `projects.json`, eliminate manager's runtime-only registry
- **Embed supervisor and issue engine** — run supervisor tick loop and issue manager as FastAPI background tasks
- **Single CLI entry point** — `set-core serve` replaces both `set-orch-core serve` and `set-manager serve`
- **Plugin route registry** — entry_points-based API route discovery for external modules
- **Remove set-manager service** — the standalone aiohttp service is no longer needed

## Capabilities

### New Capabilities

- `unified-api-server` — single FastAPI server hosting all API routes, SPA, supervisor, and issue engine
- `api-plugin-registry` — entry_points-based route registration for external modules

### Modified Capabilities

- `web-dashboard-api` — routes reorganized into domain modules, same endpoints

## Impact

- **API layer**: `lib/set_orch/api.py` split into `lib/set_orch/api/` package
- **Manager**: `lib/set_orch/manager/api.py` routes ported to FastAPI, `service.py` lifecycle embedded
- **CLI**: `bin/set-orch-core` and `bin/set-manager` deprecated, `bin/set-core` gains `serve` subcommand
- **Config**: manager's `config.yaml` project section eliminated, `projects.json` is sole registry
- **No changes to**: orchestration engine, merger, verifier, dispatcher, state, loop, issues engine logic
