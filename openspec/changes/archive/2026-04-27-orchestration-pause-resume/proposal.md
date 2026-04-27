# Proposal: orchestration-pause-resume

## Why

The orchestration system has pause/resume infrastructure in the CLI (`set-sentinel --shutdown`, `cmd_pause --all`, `cmd_resume`) and partial web UI (Settings page has Shutdown/Resume buttons), but critical gaps prevent a smooth "shutdown machine → restart → continue" workflow:

1. **Missing API endpoint**: The frontend calls `POST /api/{project}/start` for resume, but this endpoint does not exist
2. **No Resume for crash state**: The sentinel already writes `"shutdown"` on SIGUSR1 graceful stop, and the frontend shows Resume for that — but if the orchestrator crashes (state = `"stopped"`), no Resume button appears
3. **No web-initiated sentinel restart**: The Resume button has no backend to spawn a `set-sentinel` process
4. **Ralph doesn't respect shutdown signal**: Ralph loops continue iterating after the orchestrator exits — they should finish their current iteration and stop, not start a new one
5. **No shutdown progress visibility**: Users have no way to see which processes are stopping and which have finished

## What Changes

- **Add `POST /api/{project}/start` endpoint**: Spawns `set-sentinel` as a detached subprocess to resume orchestration
- **Fix frontend Resume for "stopped"**: Show Resume button for both `"stopped"` (crash) and `"shutdown"` (intentional) states
- **Ralph graceful iteration stop**: On SIGTERM, Ralph finishes current iteration then exits (no next iteration). Child processes (dev server, tests) get SIGTERM with grace period
- **Shutdown progress UI**: Web dashboard shows a live list of processes and their shutdown status (shutting down / stopped / timed out)
- **Per-change pause/resume**: Expose pause/resume per-change via API with frontend controls
- **Sentinel owns "shutdown" status**: Only the sentinel writes `"shutdown"` (already does). Engine.py always writes `"stopped"` on its own cleanup. No flag file needed — sentinel overwrites after orchestrator exits

## Capabilities

### New Capabilities
- `orchestration-lifecycle-api`: API endpoints for start/pause/resume/shutdown with status tracking and shutdown progress

### Modified Capabilities
(none — no existing specs are changing requirements)

## Impact

- `lib/set_orch/api.py` — new endpoints (start, pause change, resume change, shutdown progress)
- `lib/loop/engine.sh` — extend existing SIGTERM trap: finish iteration, stop loop, kill child processes
- `web/src/pages/Settings.tsx` — show Resume for "stopped" + "shutdown", shutdown progress list
- `web/src/lib/api.ts` — add API client functions
- `web/src/components/` — new ShutdownProgress component
- `bin/set-sentinel` — emit shutdown progress events to event log
- `lib/set_orch/engine.py` — shutdown cascade: SIGTERM to Ralph PIDs, wait, report progress

## Size

M — ~10 files, API + engine + Ralph + frontend changes
