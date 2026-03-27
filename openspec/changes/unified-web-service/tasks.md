# Tasks: Unified Web Service

## 1. API Package Structure — Moduláris Szétbontás

A monolitikus `api.py` (3147 sor) szétbontása domain-alapú modulokra.
Minden modul önálló, egy felelősséggel, saját router-rel.

```
lib/set_orch/api/
├── __init__.py         ← app factory, router registration, SPA mount
├── helpers.py          ← shared: _state_path, _resolve_project, _quick_status
├── projects.py         ← /api/projects — registry CRUD + enriched stats
├── orchestration.py    ← /api/{p}/state, changes, plans, digest, coverage, reqs
├── sessions.py         ← /api/{p}/sessions, logs, activity
├── sentinel.py         ← /api/{p}/sentinel/* (from manager)
├── issues.py           ← /api/{p}/issues/* (from manager)
├── actions.py          ← /api/{p}/approve, stop, start, pause, resume, skip
├── media.py            ← /api/{p}/screenshots, worktree logs
├── lifecycle.py        ← startup/shutdown, background supervisor + issue ticks
└── plugins.py          ← entry_points route discovery
```

- [x] 1.1 Create `api/__init__.py` — app factory: create FastAPI, mount SPA from dist/, register all domain routers, call plugin discovery [REQ: api-module-package-structure]
- [x] 1.2 Create `api/helpers.py` — extract shared helpers from api.py: `_state_path`, `_quick_status`, `_load_projects`, `_resolve_project`, `_enrich_changes`, `_claude_mangle`, `_with_state_lock`, `_load_archived_changes` [REQ: api-module-package-structure]
- [x] 1.3 Create `api/projects.py` — move project list/CRUD from api.py, enriched stats (changes_merged, tokens, active_seconds), add/remove project writes to projects.json [REQ: unified-project-registry]
- [x] 1.4 Create `api/orchestration.py` — move routes: `/api/{p}/state`, `changes/*`, `plans`, `digest`, `coverage-report`, `requirements`, `events`, `settings`, `memory` [REQ: api-module-package-structure]
- [x] 1.5 Create `api/sessions.py` — move routes: `/api/{p}/sessions/*`, `changes/*/session`, `changes/*/sessions`, `changes/*/logs`, `log`, `activity` + all session parsing helpers [REQ: api-module-package-structure]
- [x] 1.6 Create `api/actions.py` — move routes: `/api/{p}/approve`, `stop`, `start`, `shutdown`, `changes/*/pause`, `resume`, `stop`, `skip`, `processes/*` [REQ: api-module-package-structure]
- [x] 1.7 Create `api/media.py` — move routes: `/api/{p}/screenshots/*`, `worktrees/*/log/*`, `worktrees/*/reflection`, soniox-key [REQ: api-module-package-structure]

## 2. Port Manager Sentinel Routes to FastAPI

- [x] 2.1 Create `api/sentinel.py` — port from manager/api.py: `POST sentinel/start`, `stop`, `restart`, `GET sentinel/log`, `GET docs` [REQ: sentinel-routes-in-unified-server]
- [x] 2.2 Port sentinel start — read skill file, spawn via supervisor, accept `spec` parameter [REQ: sentinel-routes-in-unified-server]
- [x] 2.3 Port sentinel stop, restart, log handlers [REQ: sentinel-routes-in-unified-server]
- [x] 2.4 Port docs listing for spec autocomplete [REQ: sentinel-routes-in-unified-server]

## 3. Port Manager Issue Routes to FastAPI

- [x] 3.1 Create `api/issues.py` — port from manager/api.py: all issue CRUD, actions, groups, mutes, audit, stats [REQ: issue-routes-in-unified-server]
- [x] 3.2 Port list/get/create issues + stats + audit [REQ: issue-routes-in-unified-server]
- [x] 3.3 Port issue action routes (investigate, fix, dismiss, cancel, skip, mute, extend-timeout, message) [REQ: issue-routes-in-unified-server]
- [x] 3.4 Port group routes (list, create, fix) + mute routes (list, add, delete) [REQ: issue-routes-in-unified-server]

## 4. Unified Project Registry

- [x] 4.1 Update `api/helpers.py` `_load_projects()` to be the single source — both API list and supervisor init read from here [REQ: unified-project-registry]
- [x] 4.2 Add `_save_projects()` for project add/remove persistence [REQ: unified-project-registry]
- [x] 4.3 Remove manager's `config.py` project loading — supervisor uses shared registry [REQ: unified-project-registry]

## 5. Background Supervisor and Issue Engine

- [x] 5.1 Create `api/lifecycle.py` — FastAPI lifespan: init supervisors + issue managers for registered projects, launch tick loops as asyncio tasks [REQ: background-supervisor-lifecycle]
- [x] 5.2 Supervisor tick loop — periodic sentinel health check, exception-safe wrapper [REQ: background-supervisor-lifecycle]
- [x] 5.3 Issue manager tick loop — detection bridge + issue engine tick, exception-safe wrapper [REQ: background-supervisor-lifecycle]
- [x] 5.4 Dynamic project registration — `add_project` creates supervisor + issue manager on the fly [REQ: background-supervisor-lifecycle]

## 6. Plugin Route Registry

- [x] 6.1 Create `api/plugins.py` — discover `set_core.api_routes` entry_points, call `register_routes(router)` for each [REQ: plugin-route-discovery]
- [x] 6.2 Log discovered plugins + route count at startup [REQ: plugin-route-discovery]

## 7. CLI Unification

- [ ] 7.1 Add `serve` subcommand to `bin/set-core` — `set-core serve --port 7400` starts unified server [REQ: single-cli-entry-point]
- [ ] 7.2 Deprecation warnings in `bin/set-orch-core` and `bin/set-manager` → `set-core serve` [REQ: single-cli-entry-point]
- [ ] 7.3 Update `bin/set-restart-services` to use new entry point [REQ: single-cli-entry-point]

## 8. Cleanup and Verify

- [ ] 8.1 Delete old `lib/set_orch/api.py` (replaced by `api/` package) [REQ: api-module-package-structure]
- [ ] 8.2 Delete `lib/set_orch/manager/api.py` (routes moved to FastAPI) [REQ: api-module-package-structure]
- [ ] 8.3 Update remaining imports (web.py, CLI, tests) to use `api/` package [REQ: api-module-package-structure]
- [ ] 8.4 Build web dist + verify SPA loads on unified server [REQ: api-module-package-structure]
- [ ] 8.5 Verify all API endpoints respond identically to pre-refactor [REQ: api-route-organization]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN the server starts THEN all domain routers are registered and all existing API endpoints remain accessible [REQ: api-module-package-structure, scenario: import-and-route-registration]
- [ ] AC-2: WHEN POST /api/{p}/sentinel/start is called THEN supervisor spawns sentinel [REQ: sentinel-routes-in-unified-server, scenario: sentinel-start-via-unified-api]
- [ ] AC-3: WHEN GET /api/{p}/sentinel/log is called THEN server returns log lines [REQ: sentinel-routes-in-unified-server, scenario: sentinel-log-retrieval]
- [ ] AC-4: WHEN GET /api/{p}/issues is called THEN server returns issues from registry [REQ: issue-routes-in-unified-server, scenario: list-issues]
- [ ] AC-5: WHEN POST /api/{p}/issues/{id}/investigate is called THEN issue action executes [REQ: issue-routes-in-unified-server, scenario: issue-action]
- [ ] AC-6: WHEN project added via POST /api/projects THEN it persists to projects.json and appears in GET /api/projects [REQ: unified-project-registry, scenario: project-registered-via-api-appears-in-list]
- [ ] AC-7: WHEN server starts with registered projects THEN supervisor tick loop begins [REQ: background-supervisor-lifecycle, scenario: supervisor-runs-on-startup]
- [ ] AC-8: WHEN supervisor tick throws exception THEN error is logged and loop continues [REQ: background-supervisor-lifecycle, scenario: supervisor-survives-exceptions]
- [ ] AC-9: WHEN user runs `set-core serve --port 7400` THEN unified server starts [REQ: single-cli-entry-point, scenario: set-core-serve-starts-unified-server]
- [ ] AC-10: WHEN user runs `set-manager serve` THEN deprecation warning is printed [REQ: single-cli-entry-point, scenario: deprecated-cli-warns]
- [ ] AC-11: WHEN a plugin package has set_core.api_routes entry_point THEN its routes are registered [REQ: plugin-route-discovery, scenario: plugin-with-registered-entry-point]
- [ ] AC-12: WHEN existing orchestration endpoint is called THEN response is identical to pre-refactor [REQ: api-route-organization, scenario: existing-orchestration-routes-unchanged]
