# Design: Unified Web Service

## Context

set-core has two web services that evolved independently:
- `set-orch-core` (FastAPI/uvicorn, port 7400): SPA host + orchestration state API (~2300 lines in `api.py`)
- `set-manager` (aiohttp, port 3112): sentinel supervisor + issue management + process lifecycle

Both serve `/api/projects` but from different registries. The SPA needs data from both but can only easily call one port. The orchestration engine (`engine.py`, `merger.py`, `verifier.py`, `dispatcher.py`) is not affected — only the API/service layer changes.

## Goals / Non-Goals

**Goals:**
- Single port for the browser (SPA + all API routes)
- Single project registry (`projects.json`)
- Clean API module structure (domain-based, not monolithic)
- Plugin-extensible API routes via entry_points
- Background supervisor and issue engine in the same process

**Non-Goals:**
- Changing the orchestration engine internals
- Changing the issue engine logic (models, state machine, policy)
- Changing the SPA frontend (routes stay the same)
- Microservice architecture (this is a local dev tool)

## Decisions

### D1: FastAPI as the single framework
**Decision:** Port aiohttp routes to FastAPI, not the other way.
**Why:** FastAPI is already the larger codebase (~2300 lines vs ~300), has better typing, OpenAPI docs, and the SPA is already wired to it. The aiohttp manager routes are straightforward request handlers that port easily.
**Alternatives:** Keep aiohttp and proxy from FastAPI → adds latency and complexity for no benefit.

### D2: api/ package with domain routers
**Decision:** Split `api.py` into `lib/set_orch/api/` package:
```
api/
├── __init__.py         ← app factory, mount SPA, register routers
├── projects.py         ← /api/projects (registry CRUD)
├── orchestration.py    ← /api/{p}/state, changes, phases, plans, digest
├── sessions.py         ← /api/{p}/sessions, logs, worktree logs
├── sentinel.py         ← /api/{p}/sentinel/* (ported from manager)
├── issues.py           ← /api/{p}/issues/* (ported from manager)
├── actions.py          ← /api/{p}/approve, stop, start, pause, resume
├── media.py            ← /api/{p}/screenshots, static files
└── plugins.py          ← entry_points route discovery + registration
```
**Why:** 2300 lines in one file is unmaintainable. Domain-based split matches the natural API boundaries.

### D3: projects.json as sole registry
**Decision:** The manager reads from `~/.config/set-core/projects.json` (same as set-orch-core). The manager's `config.yaml` project section and runtime `self.config.projects` dict are eliminated.
**Why:** Two registries that diverge is the root cause of "projects missing from UI".

### D4: Background tasks for supervisor and issue engine
**Decision:** Use FastAPI's `on_event("startup")` to launch supervisor tick loop and issue manager tick loop as `asyncio.create_task` background coroutines.
**Why:** The manager's `service.py` already runs these as a sync loop. Wrapping in async with `asyncio.to_thread` or periodic `asyncio.sleep` achieves the same.

### D5: Plugin API route registration via entry_points
**Decision:** External modules register API routes via `pyproject.toml` entry_points:
```toml
[project.entry-points."set_core.api_routes"]
voice = "set_project_voice.api:register_routes"
```
The plugin provides a `register_routes(router: APIRouter)` function.
**Why:** Consistent with the existing profile plugin system (`set_tools.project_types`). No new extension mechanism needed.

### D6: Deprecate set-manager and set-orch-core CLIs
**Decision:** `set-core serve` becomes the single entry point. `set-manager` and `set-orch-core` print deprecation warnings pointing to `set-core serve`.
**Why:** Two CLIs doing overlapping things causes confusion about which to run.

## Risks / Trade-offs

- [Risk] aiohttp → FastAPI port introduces bugs in sentinel/issue routes → Mitigation: the handler logic is unchanged, only the request/response wrapper changes. Test each ported route.
- [Risk] Background supervisor in FastAPI process — crash takes down API → Mitigation: supervisor tick is already exception-safe. Wrap in try/except with restart logic.
- [Risk] Large diff — many files touched → Mitigation: the core engine is untouched. Only API layer + service lifecycle changes.

## Migration Plan

1. Create `api/` package, move existing routes module by module
2. Port manager aiohttp routes to FastAPI routers
3. Switch project registry to shared `projects.json`
4. Add supervisor + issue engine as background tasks
5. Wire `set-core serve` CLI
6. Deprecate old CLIs
7. Update web dist (same SPA, now single-port)

## Open Questions

- Should `set-restart-services` be updated or replaced with `set-core serve --restart`?
