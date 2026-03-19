# Tasks: wt-web-dashboard-v2

## Backend: API & Data

### Log Archive (log-archive)
- [x] T01: Add `_archive_worktree_logs()` function in `lib/orchestration/merger.sh` — copies `<wt>/.claude/logs/*.log` to `wt/orchestration/logs/<change-name>/` before worktree removal
- [x] T02: Call `_archive_worktree_logs` in merger.sh `cleanup_worktree()` before `git worktree remove`
- [x] T03: Update `_list_change_logs()` in `lib/set_orch/api.py` to check `wt/orchestration/logs/<change-name>/` as fallback when worktree is gone
- [x] T04: Update `_read_change_log()` in `lib/set_orch/api.py` to serve from archive dir as fallback

### Gate Output API (gate-detail)
- [x] T05: Add `build_output`, `test_output`, `smoke_output`, `review_output` fields to `ChangeInfo` TypeScript interface
- [x] T06: Ensure `_enrich_changes()` in api.py passes through gate output fields and timing fields (`gate_build_ms`, `gate_test_ms`, `gate_review_ms`, `gate_verify_ms`, `gate_total_ms`)

### Screenshot API (screenshot-gallery)
- [x] T07: Add `GET /api/{project}/changes/{name}/screenshots` endpoint — lists PNG files from `smoke_screenshot_dir` and `e2e_screenshot_dir`
- [x] T08: Mount `wt/orchestration/` as static files per project for image serving (scoped to prevent directory traversal)

### Plan API (plan-viewer)
- [x] T09: Add `GET /api/{project}/plans` endpoint — lists plan JSON files from `wt/orchestration/plans/`
- [x] T10: Add `GET /api/{project}/plans/{filename}` endpoint — returns parsed plan JSON

### Events API (token-chart)
- [x] T11: Add `GET /api/{project}/events` endpoint with `type` query param — reads `orchestration-state-events.jsonl`, filters by event type, returns JSON array

### Session Labels (session-labels)
- [x] T12: Add `_derive_session_label()` helper in api.py — reads first JSONL entry, extracts task description, returns short label (max 20 chars)
- [x] T13: Include `label` field in session objects returned by `getChangeSession` endpoint

## Frontend: Components

### Gate Detail Panel (gate-detail)
- [x] T14: Create `GateDetail.tsx` component — collapsible sections per gate (Build/Test/Review/Smoke) with monospace output display
- [x] T15: Modify `ChangeTable.tsx` — clicking gate badge or row expands to show `GateDetail` inline below the row
- [x] T16: Add gate timing display in `GateDetail` — show duration per gate from `gate_*_ms` fields

### Screenshot Gallery (screenshot-gallery)
- [x] T17: Create `ScreenshotGallery.tsx` component — thumbnail grid with click-to-enlarge lightbox
- [x] T18: Add camera icon to `GateBar.tsx` when `smoke_screenshot_count > 0` — click opens gallery
- [x] T19: Add E2E screenshots section (if phase_e2e_results exist) — organized by cycle

### Split Log Panel (split-log-panel)
- [x] T20: Refactor `LogPanel.tsx` — when change selected, split into left (orch log) and right (session log) using horizontal `ResizableSplit`
- [x] T21: Both sides get independent auto-scroll and jump-to-bottom behavior
- [x] T22: Persist horizontal split ratio to localStorage (`wt-log-split-ratio`)

### Session Labels (session-labels)
- [x] T23: Update `LogPanel.tsx` session tabs to use `label` field from API instead of `#N HH:MM`
- [x] T24: Show full task text as tooltip on session tab hover

### Cost Estimation (cost-estimation)
- [x] T25: Create `lib/pricing.ts` with model pricing table (haiku/sonnet/opus input/output/cache rates)
- [x] T26: Add `estimateCost()` utility function — takes tokens + model, returns USD
- [x] T27: Add cost display to `StatusHeader.tsx` — total estimated cost next to token counts
- [x] T28: Add Cost column to `ChangeTable.tsx` — per-change cost estimate

### Change Timeline (change-timeline)
- [x] T29: Create `ChangeTimeline.tsx` component — horizontal bar showing phases (Dispatch → Impl → Build → Test → Review → Smoke → Merge)
- [x] T30: Color phases by result (green=pass, red=fail, gray=pending, animated=current)
- [x] T31: Show phase durations on hover (tooltip with time)
- [x] T32: Integrate timeline into expanded change detail row (shown when gate detail is expanded)

### Plan Viewer (plan-viewer)
- [x] T33: Create `PlanViewer.tsx` component — table/tree of planned changes with name, complexity, scope, dependencies, change_type
- [x] T34: Add plan version selector dropdown (when multiple plans exist)
- [x] T35: Add "Plan" tab or section to Dashboard page

### Token Chart (token-chart)
- [x] T36: Create `TokenChart.tsx` component using Recharts — area chart with time X-axis and token Y-axis
- [x] T37: Fetch token events from `GET /api/{project}/events?type=TOKENS`
- [x] T38: Add chart to Dashboard page (collapsible section above or below changes table)

## Frontend: Types & Infrastructure
- [x] T39: Update `ChangeInfo` in `api.ts` — add gate output fields, screenshot fields, gate timing fields, model field
- [x] T40: Add API function types for new endpoints (screenshots, plans, events)
- [x] T41: Build and verify TypeScript passes with all new types
