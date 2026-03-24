# Proposal: manager-sentinel-launch

## Why

The manager UI has Start buttons for sentinel and orchestrator, but the sentinel prompt is a hardcoded 3-line generic message — completely disconnected from the actual `/set:sentinel` skill (380 lines of polling logic, tier system, crash recovery, checkpoint handling). The orchestrator Start button is also redundant since the sentinel skill already starts the orchestrator. Additionally, the UI shows a flat tile list with inline controls, but the production use case needs a detail view where you configure *what* to run (spec path) before launching. Finally, there is no automated E2E bootstrap script — each test run requires manual directory setup, scaffold copying, and registration.

## What Changes

- **Sentinel launch uses actual skill content**: `supervisor.py` reads `.claude/commands/set/sentinel.md` from the project directory and uses it as the `claude -p` prompt instead of the hardcoded 3-liner
- **Remove separate Orchestrator Start button**: The sentinel skill starts the orchestrator internally — a separate button is redundant and confusing
- **Manager UI: tile → detail navigation**: Tiles become clickable summary cards linking to `/manager/:project` detail view. Sentinel controls, docs listing, spec path selection, issues, and changes live in the detail view
- **Spec path input**: Detail view shows docs directory contents and provides a dropdown/autocomplete for selecting the spec path passed to the sentinel
- **New docs listing API endpoint**: `GET /api/projects/{name}/docs` returns the docs directory tree so the UI can display available specs
- **E2E bootstrap script**: `tests/e2e/run.sh` automates: create project dir, git init, copy scaffold docs, `set-project init`, register via manager API, start sentinel via API
- **Sentinel start API accepts spec parameter**: `POST /api/projects/{name}/sentinel/start` accepts `{"spec": "docs/"}` to configure the sentinel launch

## Capabilities

### New Capabilities
- `manager-project-detail` — detail view page for a single project with docs listing, sentinel control with spec selection, orchestration status, issues summary
- `e2e-bootstrap` — automated E2E test run setup script that scaffolds a project and registers it with the manager

### Modified Capabilities
- `sentinel-dashboard` — sentinel launch reads skill file instead of hardcoded prompt; accepts spec parameter
- `web-dashboard-spa` — tile cards become clickable links to detail view; remove inline orchestrator controls

## Impact

- **Backend**: `supervisor.py` (sentinel prompt loading), `api.py` (new docs endpoint, spec param on sentinel start, remove orchestrator start)
- **Frontend**: `ProjectCard.tsx` (simplify to clickable summary), new `ProjectDetail.tsx` page, new `DocsListing.tsx` component, new `SentinelControl.tsx` component with spec autocomplete, `App.tsx` routes, `api.ts` types
- **Scripts**: New `tests/e2e/run.sh`
- **No breaking changes**: The manager API sentinel/start endpoint gains an optional `spec` field — existing callers unaffected
