# Proposal: Process Manager UI

## Why

When an orchestration run finishes or needs to be stopped, there's no way to see and kill all related processes from the web UI. The user has to manually `ps aux | grep` and kill PIDs. The Settings page already shows orchestrator/sentinel PIDs but has no kill functionality, and doesn't show the full process tree (sentinel → orchestrator → ralph loops → claude agents).

## What Changes

- **Process tree API endpoint**: New `/api/:project/processes` endpoint that discovers all related processes (sentinel, orchestrator, ralph loops, claude agents) organized in a parent-child tree
- **Process manager section on Settings page**: Visual process tree with PID, uptime, CPU, memory, and a Stop button per process + a "Stop All" button that kills in correct order (agents first → orchestrator → sentinel)
- **Graceful shutdown order**: Stop All kills bottom-up (leaf agents first, then orchestrator, then sentinel) with SIGTERM and fallback to SIGKILL after timeout

## Capabilities

### New Capabilities

- `process-manager` — Process discovery, tree visualization, and graceful shutdown from web UI

### Modified Capabilities

(none)

## Impact

- **lib/set_orch/api.py** — New `/api/:project/processes` and `/api/:project/processes/:pid/stop` endpoints
- **web/src/pages/Settings.tsx** — New ProcessTree section below existing Runtime section
