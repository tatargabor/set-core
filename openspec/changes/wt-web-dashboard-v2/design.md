## Context

The wt-web dashboard v1 provides basic orchestration monitoring: state display, change table with status/tokens/gates, orch log streaming, and session JSONL viewing. Built with React + Vite + Tailwind (dark theme), served by FastAPI with WebSocket real-time updates.

Key data sources already exist but aren't surfaced in the UI:
- Gate outputs (`build_output`, `test_output` in state JSON) — full text available
- Smoke/E2E screenshots (`wt/orchestration/smoke-screenshots/`, `e2e-screenshots/`) — PNG files
- Decompose plans (`wt/orchestration/plans/plan-v*.json`) — structured JSON
- HTML report (`wt/orchestration/report.html`) — auto-refreshing standalone report
- Session JSONL first entry contains the task prompt — can derive meaningful labels

One data type is lost: worktree `.claude/logs/` are deleted when `git worktree remove` runs after merge.

## Goals / Non-Goals

**Goals:**
- Surface all existing orchestration data in the dashboard without filesystem browsing
- Preserve worktree agent logs beyond worktree lifecycle
- Show orch log and session log simultaneously (split view)
- Make session tabs meaningful (not just `#1`, `#2`)
- Provide cost visibility (token → USD)
- Visual change progress timeline

**Non-Goals:**
- Replacing `report.html` — it serves a different purpose (standalone, shareable)
- Real-time screenshot streaming — screenshots are collected post-hoc
- Editing orchestration config from UI (future work)
- Multi-project simultaneous view (future work)

## Decisions

### D1: Gate detail as expandable row, not modal
Clicking a gate badge expands the change row inline to show output text. No modal — keeps context visible. Each gate section (build, test, review, smoke) is a collapsible block within the expanded area.

### D2: Screenshot serving via static file mount
Mount `wt/orchestration/` as a static path per project. Screenshots served directly as images — no base64 encoding through API. New API endpoint lists available screenshots per change.

### D3: Log archive in merger.sh before cleanup
Add `_archive_worktree_logs()` call in `cleanup_worktree()` (merger.sh). Copies `.claude/logs/*.log` to `wt/orchestration/logs/<change-name>/`. The API already has fallback logic — extend it to check the archive dir.

### D4: Split log panel using existing ResizableSplit
Reuse `ResizableSplit` component horizontally inside the bottom panel. Left: orch log (always visible). Right: session log (when change selected). Single panel when no change selected.

### D5: Session label from JSONL first entry
Parse the first `enqueue` entry's `content` field. Extract the task line (usually starts with "# Task" or "Task:"). Truncate to ~30 chars. Fallback: `#N HH:MM` as current.

### D6: Cost calculation client-side
Token costs computed in frontend using a pricing table (haiku/sonnet/opus rates). Model field is available per change in state. No backend changes needed.

### D7: Timeline as horizontal bar in change detail
Each change gets a timeline bar showing phases: dispatched → implementing → gates (build/test/review/smoke) → merge. Timestamps from state fields (`started_at`, `completed_at`, gate timing fields like `gate_build_ms`, `gate_test_ms`).

### D8: Plan viewer reads plan JSON via new API endpoint
New endpoint `GET /api/{project}/plans` returns list of plan files. `GET /api/{project}/plans/{filename}` returns parsed JSON. Frontend renders as a tree/table of changes with dependencies and complexity.

### D9: Token chart using Recharts
Already a dependency. Chart data from `orchestration-state-events.jsonl` — TOKENS events contain cumulative token counts with timestamps. New API endpoint to serve event stream filtered by type.

## Risks / Trade-offs

- **Screenshot file serving**: Mounting project dirs as static files requires careful path validation to prevent directory traversal. Use FastAPI's `StaticFiles` with project-scoped paths.
- **Log archive disk usage**: Copying logs doubles storage temporarily. Mitigated by logs being small (typically <1MB per change) and only keeping the latest run.
- **JSONL parsing for labels**: First-entry parsing adds latency to session list loading. Mitigate by caching labels server-side or computing on first access.
- **Event JSONL size**: Token chart reads potentially large event files. Use streaming/pagination or limit to last N events.
