## Why

The `wt-orchestrate` CLI runs multi-change plans autonomously — dispatching to worktrees, monitoring Ralph loops, running verify gates, and auto-merging — but visibility into a running orchestration requires terminal commands (`wt-orchestrate status`). The wt-control GUI already shows per-worktree agent status, Ralph loop state, and token usage; adding an orchestrator view would give developers a live dashboard of the full plan lifecycle without switching to a terminal. This also enables GUI-based checkpoint approval, which currently requires running `wt-orchestrate approve` manually.

## What Changes

- **Orchestrator status badge on project header**: Detect `orchestration-state.json` in each project, show a colored badge (green=running, yellow=checkpoint/waiting, red=failed, gray=stopped/done) next to existing `[M]` and `[O]` buttons
- **Orchestrator detail dialog**: New dialog (like MemoryBrowseDialog pattern) showing the full plan — per-change cards with status, iteration count, token usage, gate results, and dependency relationships
- **Dependency graph visualization**: Visual DAG of changes with status colors, rendered via QPainter in a custom widget
- **Approve button**: When orchestrator is in "checkpoint" status, show an approve button in both the badge tooltip and the detail dialog that writes the approval signal to orchestration-state.json
- **FeatureWorker extension**: Add orchestration-state.json polling to the existing FeatureWorker (same pattern as wt-openspec and wt-memory status polling)
- **Orchestrator log viewer**: Quick access to `.claude/orchestration.log` from the detail dialog

## Capabilities

### New Capabilities
- `orchestrator-gui`: Orchestrator status badge, detail dialog with change cards and dependency graph, checkpoint approval button, log viewer — all integrated into the existing wt-control GUI

### Modified Capabilities
- `control-center`: Add orchestrator badge to project header row, extend FeatureWorker to poll orchestration state

## Impact

- **New files**: `gui/dialogs/orchestrator.py` (detail dialog + DAG widget), `gui/workers/` updates to FeatureWorker
- **Modified files**: `gui/control_center/mixins/table.py` (badge rendering), `gui/control_center/mixins/menus.py` (context menu), `gui/workers/feature.py` (orchestration polling), `gui/constants.py` (orchestrator colors)
- **Data source**: Reads `orchestration-state.json` (project root) and per-worktree `.claude/loop-state.json` (already read by GUI)
- **No new dependencies**: Uses existing PySide6/QPainter, no additional packages
- **No CLI changes**: The orchestrator CLI (`wt-orchestrate`) is not modified — GUI reads its state files
