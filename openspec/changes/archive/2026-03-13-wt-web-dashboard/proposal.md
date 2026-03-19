## Why

The orchestration pipeline generates rich runtime data (change status, token usage, gate results, logs) that is currently only accessible through three disconnected interfaces: a PySide6 desktop GUI (worktree management), a Textual TUI (live orchestration monitoring), and a static HTML report (bash-generated, auto-refresh every 15s). None of these support interactive control — approving checkpoints, stopping changes, or triggering replans requires CLI commands or direct JSON file editing. A unified web dashboard would replace the static HTML report with a real-time, interactive interface for monitoring and controlling orchestration across multiple projects.

## What Changes

- Create a FastAPI backend in `lib/set_orch/` that exposes the existing Python core (state, process, templates) as REST + WebSocket endpoints
- Add file-watching capability to push state/log changes to connected clients in real-time
- Create a Vite + React SPA in `web/` with an orchestration dashboard, project selector, and control panel
- Add `set-orch-core serve` subcommand that starts the API server with static file serving
- Add systemd user service for always-on background operation
- Integrate into `install.sh` for automatic service deployment
- Replace the bash HTML report generator (`reporter.sh generate_report()`) with the web dashboard as the primary reporting interface
- Add browser notification support for checkpoint and error events

## Capabilities

### New Capabilities
- `web-api-server`: FastAPI backend serving orchestration state, change data, worktree info, and agent activity over REST endpoints; WebSocket streaming for real-time state and log updates; write endpoints for approve, stop, skip, and replan operations; multi-project support via projects.json registry
- `web-dashboard-spa`: Vite + React SPA with orchestration live dashboard (change table, token tracking, gate visualization, log streaming), project selector, worktree overview, and browser notifications for checkpoints/errors
- `web-service-lifecycle`: systemd user service for always-on operation, `set-orch-core serve` CLI entry point, install.sh integration for automatic deployment

### Modified Capabilities
- `orchestration-engine`: The `set-orch-core` CLI gains a `serve` subcommand; `cli.py` extended with server bootstrap

## Impact

- **New files:** `lib/set_orch/api.py`, `lib/set_orch/watcher.py`, `lib/set_orch/server.py`, `web/` (Vite React SPA), systemd service file
- **Modified:** `lib/set_orch/cli.py` (add `serve` subcommand), `install.sh` (systemd deployment), `pyproject.toml` (fastapi, uvicorn, watchfiles deps)
- **Replaced:** `lib/orchestration/reporter.sh generate_report()` output superseded by web dashboard (reporter.sh remains for backward compat but web is primary)
- **Dependencies:** fastapi, uvicorn, watchfiles (Python); react, vite, tailwindcss, shadcn/ui, recharts (npm, in web/)
- **No breaking changes** to CLI, orchestration flow, or existing TUI — the web dashboard is additive
