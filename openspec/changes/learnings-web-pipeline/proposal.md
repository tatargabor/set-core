# Proposal: learnings-web-pipeline

## Why

The orchestration system captures valuable learning data at multiple points — agent reflections after each iteration, review findings during gate verification, gate pass/fail statistics, and sentinel findings — but this data is fragmented across files, partially dead-coded, and invisible on the web dashboard. Key feedback loops are broken: reflections are written but never read back into subsequent iterations, review findings are logged to JSONL but never fed into retry prompts, and `orch_remember()`/`orch_recall()` are defined but called nowhere. The web dashboard has no "Learnings" view despite having all the raw ingredients.

## What Changes

- **FIX**: Wire `get_previous_iteration_summary()` (defined at loop_prompt.py:202 but never called) into `build_claude_prompt()` (loop_prompt.py:23) to inject prior reflection into agent prompts
- **FIX**: Feed review findings JSONL into `_build_unified_retry_context()` so retry prompts include structured prior findings
- **FIX**: Connect `orch_remember()` calls at run terminal states to persist gate stats, review pattern summaries, and merge conflict info to memory
- **NEW**: API endpoints for review findings, gate stats aggregation, reflections aggregation, and per-change timeline
- **NEW**: Unified `/api/{project}/learnings` endpoint combining all learning sources
- **NEW**: `LearningsPanel` web component with expandable sections for reflections, review findings, gate performance, and sentinel findings
- **NEW**: Per-change timeline detail view showing state transitions from events.jsonl with gate results per attempt
- **ENHANCE**: Worktrees page shows reflection preview when `has_reflection` flag is true

## Capabilities

### New Capabilities
- `learnings-api`: Unified API layer for all learning data sources (reflections, review findings, gate stats, timeline)
- `learnings-web-panel`: Web dashboard component aggregating and displaying all orchestration learnings with drill-down

### Modified Capabilities
- `agent-self-reflection`: Wire reflection read-back into iteration prompt (fix broken feedback loop)
- `structured-retry-context`: Include review findings JSONL in retry context (fix missing data source)
- `orchestrator-memory`: Connect `orch_remember()` calls at terminal states (activate dead code)
- `change-timeline`: Add per-change timeline API endpoint sourced from events.jsonl state transitions
- `web-dashboard-spa`: Add Learnings tab and reflection preview in Worktrees page

## Impact

- **Files modified**: `lib/set_orch/loop_prompt.py`, `lib/set_orch/verifier.py`, `lib/set_orch/engine.py`, `lib/set_orch/merger.py`, `lib/set_orch/orch_memory.py`, `lib/set_orch/api.py`, `web/src/lib/api.ts`, `web/src/pages/Dashboard.tsx`, `web/src/pages/Worktrees.tsx`
- **New files**: `web/src/components/LearningsPanel.tsx`, `web/src/components/ChangeTimelineDetail.tsx`
- **Risk**: Feedback loop changes (reflection injection, retry context) affect agent behavior — changes are additive (extra context) so risk is low
- **Dependencies**: No new packages — recharts already available for charts
