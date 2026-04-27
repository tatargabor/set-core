# Projects Overview

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Project cards showing sentinel/orchestrator status
- Start/stop/restart controls for sentinel and orchestrator per project
- Mode badge (E2E/PROD/DEV)
- Issue count summary with nearest timeout
- Manager service health bar
- Auto-refresh every 5 seconds

### Out of scope
- Project registration from UI (use CLI: `set-manager project add`)
- Project deletion from UI
- Orchestration configuration/plan editing

## Requirements

### Requirement: Project cards
The overview page SHALL display a card for each registered project showing: name, mode badge, sentinel status (alive/stopped + uptime), orchestrator status (alive/stopped + uptime), change progress (if orchestrating), and issue summary.

#### Scenario: Active project display
- **WHEN** the overview page loads and a project has running sentinel and orchestrator
- **THEN** green indicators show with uptime, and issue counts are displayed

#### Scenario: Stopped project display
- **WHEN** a project has no running processes
- **THEN** gray "stopped" indicators show with Start buttons

### Requirement: Process control buttons
Each project card SHALL have Start/Stop/Restart buttons for both sentinel and orchestrator. Buttons SHALL call the set-manager API and update status on response.

#### Scenario: Start sentinel from UI
- **WHEN** user clicks "Start" next to a stopped sentinel
- **THEN** POST /api/projects/{name}/sentinel/start is called and the indicator updates to green

#### Scenario: Stop orchestrator from UI
- **WHEN** user clicks "Stop" next to a running orchestrator
- **THEN** POST /api/projects/{name}/orchestration/stop is called and the indicator updates to gray

### Requirement: Service health display
The page SHALL show a status bar indicating set-manager service health: running/stopped, uptime, tick interval.

#### Scenario: Manager running
- **WHEN** GET /api/manager/status returns successfully
- **THEN** a green health bar shows uptime and tick interval

#### Scenario: Manager unreachable
- **WHEN** GET /api/manager/status fails
- **THEN** a red banner shows "set-manager is not running" with CLI instructions
