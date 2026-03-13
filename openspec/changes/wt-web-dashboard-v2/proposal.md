## Why

The wt-web dashboard (v1) provides basic orchestration monitoring but is missing critical visibility into gate results, screenshots, agent logs, and cost. Users currently need to browse the filesystem or open `report.html` separately to see smoke screenshots, build/test output, or plan details. Worktree agent logs are permanently lost after merge. The log panel shows either orch log or session log but never both simultaneously.

## What Changes

- **Gate detail panel**: Clicking a gate badge (T/B/R/S) expands to show full build/test/smoke output text from the state file
- **Screenshot gallery**: Inline viewing of smoke and E2E screenshots stored in `wt/orchestration/smoke-screenshots/` and `e2e-screenshots/`
- **Log archive**: Copy worktree `.claude/logs/` to `wt/orchestration/logs/<change>/` before worktree removal so agent iteration logs survive merge
- **Split log panel**: Orch log and session log side-by-side instead of tab switching
- **Session labeling**: Parse first JSONL entry to derive meaningful session tab names (e.g., "Impl #1", "Build fix", "Verify")
- **Cost estimation**: Calculate approximate USD cost from token counts using model pricing
- **Change timeline**: Visual timeline bar showing dispatch → build → test → verify → merge phases with timestamps
- **Plan viewer**: Display decompose plan JSON in a structured view
- **Token burn chart**: Time-series chart of token consumption using Recharts (already a dependency)
- **Done-state session fix**: Ensure session count displays correctly for completed/merged changes

## Capabilities

### New Capabilities
- `gate-detail`: Expandable gate result panel showing full build/test/smoke/review output
- `screenshot-gallery`: Inline image viewer for smoke and E2E Playwright screenshots
- `log-archive`: Persist worktree agent logs beyond worktree lifecycle
- `split-log-panel`: Side-by-side orchestration log and session log view
- `session-labels`: Meaningful session tab names derived from JSONL content
- `cost-estimation`: Token-to-USD cost calculation and display
- `change-timeline`: Visual phase timeline for each change
- `plan-viewer`: Structured display of decompose plan JSON
- `token-chart`: Time-series token consumption chart

### Modified Capabilities

## Impact

- **Backend (lib/wt_orch/)**: New API endpoints for screenshots, gate output, plan data. Log archive hook in merger/dispatcher.
- **Frontend (web/src/)**: New components for gate detail, screenshot gallery, timeline, chart. LogPanel restructured for split view.
- **Orchestrator (lib/orchestration/)**: merger.sh modified to archive logs before worktree cleanup.
- **Dependencies**: No new deps — Recharts already included.
