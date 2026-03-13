## Context

The orchestration engine (`lib/orchestration/*.sh`) manages parallel AI agent workflows. Runtime data flows through JSON files: `orchestration-state.json` (global state), per-worktree `loop-state.json` (iteration progress), and `orchestration.log` (event stream). The recently completed `orchestration-python-core` change created `lib/wt_orch/` with typed dataclasses (`OrchestratorState`, `Change`, `WatchdogState`), atomic file I/O (`load_state`/`save_state`), process management (`check_pid`, `safe_kill`, `find_orphans`), and a CLI bridge (`bin/wt-orch-core`).

Current UI interfaces:
- **PySide6 GUI** (`gui/`, 42K lines) — desktop systemtray app for worktree management, chat, memory
- **Textual TUI** (`gui/tui/orchestrator_tui.py`, 665 lines) — live terminal dashboard, read-only except checkpoint approve
- **Bash HTML report** (`lib/orchestration/reporter.sh`, 740 lines) — static HTML with 15s auto-refresh, no interactivity

Multi-project support exists via `~/.config/wt-tools/projects.json` registry (used by `wt-project` CLI).

The bash orchestration checkpoint flow uses file-based polling: `state.sh` loops every 10 seconds checking `orchestration-state.json` for `.checkpoints[-1].approved == true`. Any process that writes this field (TUI, CLI, or the new web API) unblocks the orchestration.

## Goals / Non-Goals

**Goals:**
- Serve orchestration state, changes, worktrees, and agent activity over REST + WebSocket
- Push real-time updates to connected web clients when state/log files change
- Provide interactive control: approve checkpoints, stop/skip changes, stop orchestration, trigger replan
- Serve a Vite+React SPA as the primary orchestration dashboard
- Support multiple projects via the existing projects.json registry
- Run as a systemd user service — always available at `localhost:7400`
- Browser notifications for checkpoints and errors

**Non-Goals:**
- Replacing the PySide6 desktop GUI (it stays for systemtray, quick-access)
- Replacing the Textual TUI (it stays for terminal-only environments)
- Remote/cloud deployment (localhost only, no auth)
- Mobile-responsive design (desktop browser is the target)
- Real-time editing of orchestration config (read config, write control commands only)
- Removing `reporter.sh` (it remains for backward compat, but web dashboard is primary)

## Decisions

### D1: Backend framework — FastAPI + uvicorn

FastAPI provides async HTTP + WebSocket in a single framework. uvicorn is the standard ASGI server. Both are well-supported, lightweight, and already familiar in the Python ecosystem.

```
lib/wt_orch/
├── cli.py        ← existing, add cmd_serve()
├── state.py      ← existing, reused by API
├── process.py    ← existing, reused by API
├── api.py        ← NEW: FastAPI routes
├── watcher.py    ← NEW: file change detection
└── server.py     ← NEW: app factory + static serving
```

**Alternative considered:** Extending the existing MCP server (`mcp-server/`). Rejected — the MCP server serves Claude tools via stdio/SSE protocol, not HTTP. Adding HTTP endpoints there would conflate two different purposes.

**Alternative considered:** Flask. Rejected — no native async/WebSocket support, would need additional libraries (flask-socketio, gevent).

### D2: File watching — watchfiles (Rust-based)

`watchfiles` uses Rust's `notify` crate for filesystem events. It's fast, cross-platform, and integrates with asyncio natively.

```python
# watcher.py concept
async def watch_project(project_path, callback):
    paths = [
        project_path / "wt/orchestration/orchestration-state.json",
        project_path / "wt/orchestration/orchestration.log",
    ]
    async for changes in awatch(*paths):
        await callback(changes)
```

When a file change is detected:
1. Read new state via `load_state()` (existing function)
2. Diff against last known state (new changes, status transitions)
3. Push delta to all connected WebSocket clients

**Alternative considered:** Polling with `asyncio.sleep(2)`. Rejected — adds latency and CPU overhead. The TUI already polls at 3s intervals; the web should be better, not the same.

### D3: WebSocket protocol — JSON messages with event types

```json
{"event": "state_update", "data": {"status": "running", "changes": [...]}}
{"event": "log_lines", "data": {"lines": ["[INFO] ...", "[WARN] ..."]}}
{"event": "checkpoint_pending", "data": {"checkpoint_id": 3, "completed": 4, "total": 7}}
{"event": "change_complete", "data": {"name": "add-auth", "status": "done"}}
{"event": "error", "data": {"message": "Process crashed", "change": "add-cart"}}
```

Clients connect to `/ws/{project_name}/stream`. On connect, they receive the full current state. After that, only deltas are pushed.

### D4: API endpoint structure

```
READ endpoints (GET):
  /api/projects                      → list from projects.json
  /api/{project}/state               → full orchestration state
  /api/{project}/changes             → changes array with optional ?status= filter
  /api/{project}/changes/{name}      → single change detail
  /api/{project}/worktrees           → git worktree list + loop-state
  /api/{project}/activity            → agent activity.json per worktree
  /api/{project}/log                 → last N lines of orchestration.log
  /api/{project}/config              → orchestration.yaml (read-only)

WRITE endpoints (POST):
  /api/{project}/approve             → approve latest checkpoint
  /api/{project}/stop                → stop orchestration (safe_kill on main PID)
  /api/{project}/changes/{name}/stop → stop single change (safe_kill on ralph_pid)
  /api/{project}/changes/{name}/skip → mark change as skipped
  /api/{project}/replan              → trigger replan by writing replan marker

WebSocket:
  /ws/{project}/stream               → real-time state + log push
```

Write operations use `save_state()` (existing atomic write) and `safe_kill()` (existing process management). The flock-based `with_state_lock` is respected — the API acquires the same lock before writing.

**Decision:** The API writes to the same `orchestration-state.json` that bash reads. No new IPC mechanism. The bash orchestration already polls this file — any write is picked up within 10 seconds (checkpoint polling interval).

### D5: Frontend — Vite + React SPA with Tailwind + shadcn/ui

```
web/
├── src/
│   ├── App.tsx                  ← router, layout, project context
│   ├── pages/
│   │   ├── Dashboard.tsx        ← orchestration live view (primary)
│   │   ├── Worktrees.tsx        ← worktree list, agent activity
│   │   └── Settings.tsx         ← project config viewer
│   ├── components/
│   │   ├── ProjectSelector.tsx  ← dropdown from /api/projects
│   │   ├── ChangeTable.tsx      ← status, tokens, gates, duration
│   │   ├── GateBar.tsx          ← T/B/E/R/V/S gate visualization
│   │   ├── TokenChart.tsx       ← recharts token usage over time
│   │   ├── LogStream.tsx        ← virtual scrolling log viewer
│   │   ├── CheckpointBanner.tsx ← approve/stop/replan controls
│   │   └── StatusHeader.tsx     ← orchestration status, timing, totals
│   ├── hooks/
│   │   ├── useWebSocket.ts      ← WS connection + reconnect
│   │   ├── useProject.ts        ← current project context
│   │   └── useNotifications.ts  ← browser Notification API
│   └── lib/
│       └── api.ts               ← fetch wrappers for REST endpoints
├── package.json
├── vite.config.ts               ← proxy /api → FastAPI in dev
├── tailwind.config.ts
└── tsconfig.json
```

**Why not Next.js:** No SSR/SSG needed (localhost tool, no SEO). Vite gives faster HMR (~200ms vs 1-2s), simpler mental model (pure SPA), and smaller bundle. The API is Python-based, not Node.

**Why shadcn/ui:** Copy-paste component library, no runtime dependency. Works with Tailwind. Good defaults for tables, buttons, dialogs.

**Why Recharts:** Lightweight charting for token usage visualization. React-native, composable.

### D6: Static file serving — FastAPI serves built SPA

In production (systemd service), FastAPI serves the pre-built SPA from `web/dist/`:

```python
# server.py
app.mount("/", StaticFiles(directory="web/dist", html=True))
```

In development, Vite dev server runs separately with proxy to FastAPI:

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/api': 'http://localhost:7400',
      '/ws': { target: 'ws://localhost:7400', ws: true }
    }
  }
})
```

### D7: Multi-project — projects.json as source of truth

The server reads `~/.config/wt-tools/projects.json` at startup and watches it for changes. Each project entry has a `path` — the server validates the path exists and checks for `wt/orchestration/orchestration-state.json` to determine if orchestration is active.

```python
@app.get("/api/projects")
async def list_projects():
    projects = load_projects_registry()
    return [{
        "name": p["name"],
        "path": p["path"],
        "has_orchestration": (Path(p["path"]) / "wt/orchestration/orchestration-state.json").exists(),
        "status": get_quick_status(p["path"])  # "running" / "done" / "idle"
    } for p in projects]
```

### D8: systemd user service — always-on with auto-restart

```ini
# ~/.config/systemd/user/wt-web.service
[Unit]
Description=wt-tools Web Dashboard
After=default.target

[Service]
ExecStart=%h/.local/bin/wt-orch-core serve --port 7400
Restart=always
RestartSec=5
Environment=PYTHONPATH=%h/code2/wt-tools/lib

[Install]
WantedBy=default.target
```

`install.sh` deploys and enables this service. The port is configurable via `--port` flag or `WT_WEB_PORT` env var, defaulting to 7400.

### D9: Browser notifications — Notification API

The web client requests notification permission on first visit. When a WebSocket push arrives with `checkpoint_pending` or `error` event type, a browser notification is shown if the tab is not focused.

No external push service — this is pure browser Notification API. Works only when the tab is open (even if backgrounded). For desktop push when browser is closed, the PySide6 tray app already handles that path.

### D10: State locking — reuse flock mechanism

Write operations (approve, stop) must coordinate with the bash orchestration which uses `flock` on the state file. The Python API acquires the same flock before writing:

```python
import fcntl

def with_state_flock(state_path, fn):
    lock_path = state_path + ".lock"
    with open(lock_path, 'w') as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            return fn()
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
```

This ensures the web API and bash `with_state_lock` never corrupt state.json with concurrent writes.

## Risks / Trade-offs

**[Risk: Port conflict]** Port 7400 may be in use. → Mitigation: Configurable via `--port` / `WT_WEB_PORT`. Server logs clear error on bind failure.

**[Risk: Stale watcher]** watchfiles may miss rapid file changes. → Mitigation: Client can manually refresh via REST. WebSocket reconnect triggers full state push.

**[Risk: Large log files]** orchestration.log can grow to 10MB+. → Mitigation: Log endpoint returns last N lines (default 500). WebSocket streams only new lines (tail -f semantics). Frontend uses virtual scrolling.

**[Risk: Multiple writers]** Web API + TUI + bash all write state.json. → Mitigation: All use the same flock mechanism. Atomic write (tempfile + rename) prevents partial reads.

**[Risk: Service not running]** User expects dashboard but service crashed. → Mitigation: systemd `Restart=always` auto-recovers. `wt-orch-core serve` also works as manual foreground command for debugging.

**[Risk: npm in wt-tools]** Adding a `web/` directory with package.json introduces Node.js as a build dependency. → Mitigation: The built SPA (`web/dist/`) is committed to git. Users who don't develop the frontend never need Node.js. Only `pip install` deps (fastapi, uvicorn, watchfiles) are runtime requirements.
