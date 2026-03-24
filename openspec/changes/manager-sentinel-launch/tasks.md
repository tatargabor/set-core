# Tasks: manager-sentinel-launch

## 1. Backend — Sentinel skill-based launch

- [ ] 1.1 Modify `supervisor.py` `start_sentinel()` to read `.claude/commands/set/sentinel.md` from project path and use as prompt [REQ: sentinel-launch-uses-skill-file]
- [ ] 1.2 Add fallback to hardcoded `SENTINEL_PROMPT` with warning log when skill file not found [REQ: sentinel-launch-uses-skill-file]
- [ ] 1.3 Increase `--max-turns` from 200 to 500 in the `claude -p` command [REQ: sentinel-launch-uses-skill-file]
- [ ] 1.4 Accept `spec` parameter in `start_sentinel()` and append `\n\nArguments: --spec {spec}` to prompt when provided [REQ: sentinel-start-api-accepts-spec-parameter]
- [ ] 1.5 Update `handle_sentinel_start` in `api.py` to parse `spec` from request body and pass to `start_sentinel()` [REQ: sentinel-start-api-accepts-spec-parameter]

## 2. Backend — Remove orchestrator API

- [ ] 2.1 Remove `handle_orch_start` and `handle_orch_stop` handlers from `api.py` [REQ: remove-separate-orchestrator-start-stop-api]
- [ ] 2.2 Remove orchestration start/stop route registrations from `create_api()` [REQ: remove-separate-orchestrator-start-stop-api]
- [ ] 2.3 Keep `start_orchestration()` and `stop_orchestration()` methods on `ProjectSupervisor` (used internally by health_check) [REQ: remove-separate-orchestrator-start-stop-api]

## 3. Backend — Docs listing API

- [ ] 3.1 Add `handle_list_docs` handler in `api.py` that walks project's `docs/` directory (max 2 levels) and returns file/dir list [REQ: docs-listing-api-endpoint]
- [ ] 3.2 Register route `GET /api/projects/{name}/docs` in `create_api()` [REQ: docs-listing-api-endpoint]

## 4. Frontend — Tile overview simplification

- [ ] 4.1 Remove `ProcessControl` component usage from `ProjectCard.tsx` [REQ: manager-overview-page]
- [ ] 4.2 Make `ProjectCard` a clickable `Link` to `/manager/:project` [REQ: manager-overview-page]
- [ ] 4.3 Show summary info on tile: name, mode badge, sentinel status (running/idle), progress if running [REQ: manager-overview-page]
- [ ] 4.4 Remove `startOrchestration`/`stopOrchestration` imports from `ProjectCard.tsx` [REQ: manager-overview-page]

## 5. Frontend — Project detail page

- [ ] 5.1 Create `ProjectDetail.tsx` page component at `web/src/pages/ProjectDetail.tsx` [REQ: project-detail-page-route]
- [ ] 5.2 Add route `/manager/:project` in `App.tsx` rendering `ProjectDetail` [REQ: project-detail-page-route]
- [ ] 5.3 Add `useProjectDetail` hook that fetches project status, docs list, and orchestration summary [REQ: project-detail-page-route]
- [ ] 5.4 Implement status section showing sentinel state (running/idle, PID, uptime, crash count) [REQ: project-detail-page-route]
- [ ] 5.5 Implement docs listing section showing file tree from `/api/projects/{name}/docs` [REQ: docs-directory-listing]
- [ ] 5.6 Add back navigation link to `/manager` overview [REQ: project-detail-page-route]

## 6. Frontend — Sentinel control with spec selection

- [ ] 6.1 Create `SentinelControl.tsx` component with Start/Stop/Restart buttons [REQ: sentinel-control-with-spec-selection]
- [ ] 6.2 Add spec path input with dropdown/autocomplete populated from docs listing top-level dirs [REQ: sentinel-control-with-spec-selection]
- [ ] 6.3 Wire Start button to `POST /api/projects/{name}/sentinel/start` with `{"spec": selectedPath}` [REQ: sentinel-control-with-spec-selection]
- [ ] 6.4 Show orchestration status summary when `orchestration-state.json` data is available [REQ: orchestration-status-display]
- [ ] 6.5 Add issues summary with link to `/manager/:project/issues` [REQ: project-detail-page-route]

## 7. Frontend — API types update

- [ ] 7.1 Add `getProjectDocs(name)` function to `api.ts` [REQ: docs-listing-api-endpoint]
- [ ] 7.2 Update `startSentinel(project, spec?)` to accept optional spec parameter [REQ: sentinel-start-api-accepts-spec-parameter]
- [ ] 7.3 Remove `startOrchestration` and `stopOrchestration` exports from `api.ts` [REQ: remove-separate-orchestrator-start-stop-api]
- [ ] 7.4 Add `DocsListing` type interface [REQ: docs-listing-api-endpoint]

## 8. E2E bootstrap script

- [ ] 8.1 Create `tests/e2e/run.sh` with scaffold name argument parsing [REQ: e2e-bootstrap-script]
- [ ] 8.2 Implement auto-increment run naming (find highest existing run-N, increment) [REQ: run-naming-with-auto-increment]
- [ ] 8.3 Implement project directory creation, git init, scaffold docs copy [REQ: e2e-bootstrap-script]
- [ ] 8.4 Run `set-project init --project-type web --name $RUN_NAME` in the new directory [REQ: e2e-bootstrap-script]
- [ ] 8.5 Register project with manager API: `POST /api/projects` [REQ: manager-api-registration]
- [ ] 8.6 Start sentinel via manager API: `POST /api/projects/{name}/sentinel/start` with spec [REQ: sentinel-start-via-api]
- [ ] 8.7 Add manager health check before registration (exit with error if not running) [REQ: manager-api-registration]
- [ ] 8.8 Print monitor URL and run directory on success [REQ: e2e-bootstrap-script]

## Acceptance Criteria (from spec scenarios)

- [ ] AC-1: WHEN user clicks a project tile on the manager overview THEN browser navigates to `/manager/:project` showing the detail view [REQ: project-detail-page-route, scenario: navigate-to-project-detail]
- [ ] AC-2: WHEN user navigates directly to `/manager/craftbrew` THEN the detail view loads for project "craftbrew" [REQ: project-detail-page-route, scenario: direct-url-access]
- [ ] AC-3: WHEN user navigates to `/manager/nonexistent` THEN the page displays a not-found error [REQ: project-detail-page-route, scenario: project-not-found]
- [ ] AC-4: WHEN detail page loads for a project with docs THEN the Docs section displays the file tree [REQ: docs-directory-listing, scenario: project-has-docs]
- [ ] AC-5: WHEN detail page loads for a project with no docs THEN the Docs section shows "no docs found" [REQ: docs-directory-listing, scenario: project-has-no-docs]
- [ ] AC-6: WHEN client sends GET /api/projects/test/docs THEN response contains docs array [REQ: docs-listing-api-endpoint, scenario: list-docs-for-project]
- [ ] AC-7: WHEN user selects spec path and clicks Start THEN sentinel starts with that spec [REQ: sentinel-control-with-spec-selection, scenario: start-sentinel-with-spec-path]
- [ ] AC-8: WHEN supervisor starts sentinel THEN it reads .claude/commands/set/sentinel.md as prompt [REQ: sentinel-launch-uses-skill-file, scenario: skill-file-exists]
- [ ] AC-9: WHEN skill file not found THEN supervisor falls back to hardcoded prompt with warning [REQ: sentinel-launch-uses-skill-file, scenario: skill-file-not-found]
- [ ] AC-10: WHEN sentinel start request includes spec THEN prompt includes spec argument [REQ: sentinel-start-api-accepts-spec-parameter, scenario: start-with-spec]
- [ ] AC-11: WHEN client sends POST orchestration/start THEN server returns 404 [REQ: remove-separate-orchestrator-start-stop-api, scenario: orchestrator-endpoints-removed]
- [ ] AC-12: WHEN manager overview renders THEN tiles do NOT contain Start/Stop buttons [REQ: manager-overview-page, scenario: no-inline-process-controls-on-tiles]
- [ ] AC-13: WHEN user runs `./tests/e2e/run.sh craftbrew` THEN a new project is created, initialized, registered, and sentinel started [REQ: e2e-bootstrap-script, scenario: bootstrap-craftbrew-run]
- [ ] AC-14: WHEN no previous runs exist for scaffold THEN the run is named "craftbrew-run1" [REQ: run-naming-with-auto-increment, scenario: first-run-for-scaffold]
- [ ] AC-15: WHEN manager API is not reachable THEN run.sh exits with error [REQ: manager-api-registration, scenario: manager-not-running]
