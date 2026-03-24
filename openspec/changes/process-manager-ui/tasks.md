# Tasks: Process Manager UI

## 1. Process Discovery API

- [x] 1.1 Add `_process_info(pid)` helper in api.py — returns dict with pid, command, uptime_seconds, cpu_percent, memory_mb using `ps` [REQ: process-discovery-api]
- [x] 1.2 Add `_get_process_children(pid)` helper — uses `ps --ppid` to find child PIDs recursively [REQ: process-discovery-api]
- [x] 1.3 Add `_build_process_tree(project_path)` — reads sentinel.pid + orchestrator.pid from `.set/`, builds tree [REQ: process-discovery-api]
- [x] 1.4 Add GET `/api/:project/processes` endpoint returning the process tree [REQ: process-discovery-api]

## 2. Process Stop API

- [x] 2.1 Add POST `/api/:project/processes/:pid/stop` endpoint — sends SIGTERM to specific PID [REQ: process-stop-api]
- [x] 2.2 Add POST `/api/:project/processes/stop-all` endpoint — stops bottom-up with SIGTERM, 3s wait, SIGKILL fallback [REQ: process-stop-api]
- [x] 2.3 Set orchestration state to "stopped" after stop-all completes [REQ: process-stop-api]

## 3. Frontend — Process Tree Component

- [x] 3.1 Add `getProcesses(project)`, `stopProcess(project, pid)`, `stopAllProcesses(project)` API functions in api.ts [REQ: process-tree-ui]
- [x] 3.2 Create `ProcessTree.tsx` component — recursive tree with indentation, PID, command, uptime, CPU%, memory, Stop button [REQ: process-tree-ui]
- [x] 3.3 Add "Stop All" button with confirmation and loading state [REQ: process-tree-ui]
- [x] 3.4 Add 5s auto-refresh polling for process tree [REQ: process-tree-ui]
- [x] 3.5 Integrate ProcessTree into Settings page after Runtime section [REQ: process-tree-ui]

## 4. Build & Verify

- [x] 4.1 TypeScript compile check — 0 errors [REQ: process-tree-ui]
- [x] 4.2 Build web dist [REQ: process-tree-ui]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN orchestration running THEN process tree shows sentinel → orchestrator → agents [REQ: process-discovery-api, scenario: running-orchestration-with-agents]
- [x] AC-2: WHEN no processes running THEN response contains empty array [REQ: process-discovery-api, scenario: no-processes-running]
- [x] AC-3: WHEN stop single process THEN SIGTERM sent and confirmed [REQ: process-stop-api, scenario: stop-single-process]
- [x] AC-4: WHEN stop all THEN processes stopped bottom-up and state set to stopped [REQ: process-stop-api, scenario: stop-all-processes]
- [x] AC-5: WHEN viewing Settings THEN process tree displayed with info and Stop buttons [REQ: process-tree-ui, scenario: process-tree-display]
- [x] AC-6: WHEN clicking Stop All THEN all processes stopped in correct order [REQ: process-tree-ui, scenario: stop-all-button]
