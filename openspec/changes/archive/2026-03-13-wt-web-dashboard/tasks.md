## 1. Python Backend — API Foundation

- [x] 1.1 Add `fastapi`, `uvicorn[standard]`, `watchfiles` to pyproject.toml dependencies
- [x] 1.2 Create `lib/set_orch/server.py` — FastAPI app factory with CORS, lifespan handler, and static file mount for `web/dist/`
- [x] 1.3 Create `lib/set_orch/api.py` — read endpoints: `GET /api/projects` (read projects.json), `GET /api/{project}/state`, `GET /api/{project}/changes`, `GET /api/{project}/changes/{name}`, `GET /api/{project}/worktrees`, `GET /api/{project}/activity`, `GET /api/{project}/log`
- [x] 1.4 Add project resolution helper — map project name to path via projects.json, validate path exists, return 404 for unknown projects
- [x] 1.5 Add worktree enrichment — for each worktree, read `loop-state.json` for iteration data and `.claude/activity.json` for agent activity

## 2. Python Backend — Write Endpoints

- [x] 2.1 Add flock-based state locking helper in `api.py` — async wrapper around fcntl.flock compatible with bash `with_state_lock`, with 10s timeout returning 503
- [x] 2.2 Add `POST /api/{project}/approve` — acquire flock, load state, verify checkpoint status, mark approved with timestamp, save atomically
- [x] 2.3 Add `POST /api/{project}/stop` — read orchestrator PID from state, call `safe_kill()` with "set-orchestrate" pattern, update state to "stopped"
- [x] 2.4 Add `POST /api/{project}/changes/{name}/stop` — read ralph_pid for the change, call `safe_kill()` with "wt-loop" pattern, update change status
- [x] 2.5 Add `POST /api/{project}/changes/{name}/skip` — acquire flock, set change status to "skipped", save atomically

## 3. Python Backend — WebSocket & File Watching

- [x] 3.1 Create `lib/set_orch/watcher.py` — async file watcher using `watchfiles.awatch()` for state.json, orchestration.log, and worktree loop-state.json files per project
- [x] 3.2 Add WebSocket connection manager — track connected clients per project, handle connect/disconnect/broadcast
- [x] 3.3 Add `WS /ws/{project}/stream` endpoint — on connect send full state; on file change push `state_update`, `log_lines`, `checkpoint_pending`, or `error` events as JSON
- [x] 3.4 Implement log tail streaming — track file offset per connection, send only new lines on change (same approach as TUI `StateReader.read_log()`)
- [x] 3.5 Add checkpoint event detection — diff old state vs new state, emit `checkpoint_pending` when status transitions to "checkpoint"

## 4. CLI Integration

- [x] 4.1 Add `serve` subcommand to `lib/set_orch/cli.py` — argparse with `--port` (default 7400, env `WT_WEB_PORT`) and `--host` (default 127.0.0.1), imports and starts uvicorn
- [x] 4.2 Add graceful shutdown handler — catch SIGTERM, close WebSocket connections, stop watchers, exit cleanly within 5s
- [x] 4.3 Create systemd user service file `templates/systemd/wt-web.service` — ExecStart pointing to set-orch-core serve, Restart=always, RestartSec=5
- [x] 4.4 Update `install.sh` — copy service file to `~/.config/systemd/user/`, run daemon-reload, enable and start service (skip if no systemd)

## 5. Frontend — Vite + React SPA Setup

- [x] 5.1 Initialize `web/` with Vite React TypeScript template (`npm create vite@latest web -- --template react-ts`)
- [x] 5.2 Install and configure Tailwind CSS v4, shadcn/ui, react-router-dom, recharts
- [x] 5.3 Configure `vite.config.ts` — dev proxy `/api` and `/ws` to `localhost:7400`
- [x] 5.4 Create `web/src/lib/api.ts` — typed fetch wrappers for all REST endpoints
- [x] 5.5 Create `web/src/hooks/useWebSocket.ts` — WebSocket connection with auto-reconnect (exponential backoff), initial state fetch on reconnect, typed event parsing
- [x] 5.6 Create `web/src/hooks/useProject.ts` — current project context (from URL param + localStorage persistence)
- [x] 5.7 Create `web/src/hooks/useNotifications.ts` — browser Notification API wrapper, request permission, show notification on checkpoint/error when tab not focused

## 6. Frontend — Dashboard Page

- [x] 6.1 Create `web/src/App.tsx` — react-router layout with sidebar project selector and main content area
- [x] 6.2 Create `web/src/components/ProjectSelector.tsx` — dropdown from `/api/projects` with status indicators (color dot: green=running, yellow=checkpoint, gray=idle)
- [x] 6.3 Create `web/src/components/StatusHeader.tsx` — orchestration status badge, plan version, completed/total, token usage with cache breakdown, timing info
- [x] 6.4 Create `web/src/components/ChangeTable.tsx` — shadcn/ui table with columns: Name (with dep indicators), Status (color+icon), Iteration, Duration, Tokens (in/out/cache), Gates (T/B/E/R/V/S with pass/fail/skip icons and timing)
- [x] 6.5 Create `web/src/components/GateBar.tsx` — compact gate result visualization component used per-change row
- [x] 6.6 Create `web/src/components/LogStream.tsx` — virtual scrolling log viewer with color coding (ERROR=red, WARN=yellow, REPLAN=cyan), auto-scroll with "Jump to bottom" button
- [x] 6.7 Create `web/src/components/CheckpointBanner.tsx` — prominent banner with Approve, Stop, Replan buttons, loading states, confirmation dialog for destructive actions
- [x] 6.8 Create `web/src/pages/Dashboard.tsx` — compose StatusHeader + ChangeTable + LogStream + CheckpointBanner, wire to WebSocket stream and REST endpoints
- [x] 6.9 Add per-change action menu — context menu on each row with Stop (running) and Skip (pending) actions calling the corresponding API endpoints

## 7. Frontend — Secondary Pages

- [x] 7.1 Create `web/src/pages/Worktrees.tsx` — worktree list with branch, loop-state iteration, agent activity per worktree
- [x] 7.2 Create resizable split panel layout — change table (upper) + log viewer (lower) with draggable divider and collapse toggle

## 8. Build & Integration

- [x] 8.1 Add `npm run build` script in `web/package.json`, verify `web/dist/` output
- [x] 8.2 Commit `web/dist/` to git so non-Node users get the pre-built SPA
- [x] 8.3 Verify FastAPI serves `web/dist/` correctly — SPA routing (all non-API paths return index.html)
- [x] 8.4 Add `.gitignore` entries for `web/node_modules/`, `web/.vite/`

## 9. Testing

- [x] 9.1 Add Python tests for API read endpoints — mock state files, verify JSON responses and 404 handling
- [x] 9.2 Add Python tests for API write endpoints — verify flock acquisition, atomic write, state mutation for approve/stop/skip
- [x] 9.3 Add Python test for WebSocket — connect, verify initial state push, simulate file change, verify event push
- [x] 9.4 Add integration test — start server, verify `/api/projects` responds, verify static file serving of SPA
