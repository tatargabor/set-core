## 1. Color Profiles and Constants

- [ ] 1.1 Add orchestrator color keys to all four color profiles in `gui/constants.py`: `orch_running`, `orch_checkpoint`, `orch_paused`, `orch_done`, `orch_failed`, `orch_pending`, `orch_merged`, `orch_badge_bg` — ensure high_contrast profile meets 4.5:1 contrast ratio
- [ ] 1.2 Add orchestrator status mapping constant: dict mapping status strings (running/checkpoint/paused/done/failed/pending/merged/stopped/stalled/merge-blocked/dispatched) to color keys and display icons

## 2. FeatureWorker Orchestration Polling

- [ ] 2.1 In `gui/workers/feature.py`, add `_poll_orchestration()` method: for each project, check for `orchestration-state.json` at project root, parse JSON, return parsed dict or None
- [ ] 2.2 Add error handling: catch JSON parse errors, log warning, return None — poll cycle continues without crashing
- [ ] 2.3 Call `_poll_orchestration()` in the existing per-project poll loop, include result under `orchestration` key in `features_updated` signal
- [ ] 2.4 In `gui/control_center/main_window.py`, store orchestration data from `_feature_cache` (same pattern as memory/openspec cache)

## 3. Orchestrator Badge on Project Header

- [ ] 3.1 In `gui/control_center/mixins/table.py`, add `_render_orch_badge()` method: create QPushButton with `[⚙]` text, set background color based on orchestrator status from `_feature_cache`, connect click to open OrchestratorDialog
- [ ] 3.2 Call `_render_orch_badge()` in project header row rendering (next to existing `[M]` and `[O]` badges), only when orchestration data exists for the project
- [ ] 3.3 Add badge tooltip: "Orchestrating: X/Y done, Z running" — read change counts from cached orchestration state
- [ ] 3.4 Add checkpoint blink: when orchestrator status is "checkpoint", register badge for blink animation on existing blink_timer (yellow/normal toggle)

## 4. Dependency Graph Widget

- [ ] 4.1 Create `gui/widgets/dag_widget.py` with `DAGWidget(QWidget)` class: accepts a list of changes with dependencies, computes layered layout via topological sort
- [ ] 4.2 Implement `paintEvent`: draw rounded rectangle nodes per change (truncated to 20 chars), colored by status, with status icon
- [ ] 4.3 Implement edge drawing: directed arrows between dependent nodes using QPainterPath with arrowheads
- [ ] 4.4 Implement `_compute_layout()`: assign changes to columns by dependency depth (layer 0 = no deps, layer N = max dep depth + 1), distribute vertically within each column
- [ ] 4.5 Add node tooltip on hover: implement `event()` to handle QEvent.ToolTip, show full change name, status, iteration progress, token usage
- [ ] 4.6 Support color profiles: read colors from the active profile via constants, update on profile change

## 5. Orchestrator Detail Dialog

- [ ] 5.1 Create `gui/dialogs/orchestrator.py` with `OrchestratorDialog(QDialog)` class: modeless, WindowStaysOnTopHint, takes project name and initial orchestration data
- [ ] 5.2 Implement header section: QHBoxLayout with status indicator (colored dot + text), plan version label, progress ratio label, total tokens label, elapsed time label
- [ ] 5.3 Embed DAGWidget in a QScrollArea in the middle section
- [ ] 5.4 Implement change table: QTableWidget with columns Name, Status, Iteration, Tokens, Gates — populate from orchestration state changes array
- [ ] 5.5 Add change row coloring: status column uses colored icon + text matching spec (○ pending, ● running, ✓ done/merged, ✗ failed, ⚠ stalled/merge-blocked, ⏸ paused, ▶ dispatched)
- [ ] 5.6 Add change row tooltip: full name, scope (first 200 chars), worktree path, started/completed timestamps
- [ ] 5.7 Add Gates column tooltip: break down gate_test_ms, gate_review_ms, gate_verify_ms, gate_build_ms, retry count
- [ ] 5.8 Implement `update_data(data)` method: refresh all sections without closing dialog — called when FeatureWorker emits new data

## 6. Dialog Actions

- [ ] 6.1 Add "Approve Checkpoint" button: enabled only when orchestrator status is "checkpoint", highlighted color when enabled, grayed when disabled
- [ ] 6.2 Implement approve action: atomic write to orchestration-state.json (read, set `checkpoints[-1].approved = true` + `approved_at`, write to temp + rename)
- [ ] 6.3 Add "Approve + Merge" button: visible when merge_queue is non-empty at checkpoint, writes `merge_approved: true` in addition to approval
- [ ] 6.4 Add "View Log" button: open `.claude/orchestration.log` via `QDesktopServices.openUrl()` or platform file opener, show message if no log file exists
- [ ] 6.5 Add "Refresh" button: call `FeatureWorker.refresh_now()` to trigger immediate re-poll
- [ ] 6.6 Add "Close" button

## 7. Integration Wiring

- [ ] 7.1 In `gui/control_center/mixins/menus.py`, add OrchestratorDialog to context menu for project header rows: "Orchestrator..." menu item (only when orchestration data exists)
- [ ] 7.2 Wire FeatureWorker `features_updated` signal to update open OrchestratorDialog instances (store dialog reference on ControlCenter, call `update_data()` on signal)
- [ ] 7.3 Import and register OrchestratorDialog in `gui/control_center/main_window.py` — track open dialog per project to avoid duplicates (reuse existing dialog if open)

## 8. Testing

- [ ] 8.1 Create `tests/gui/test_orchestrator_dialog.py`: test OrchestratorDialog creation with mock orchestration-state.json data, verify status display, change table population, button states
- [ ] 8.2 Add DAGWidget test: verify layout computation with known dependency graph (3 nodes: A independent, B depends A, C independent), verify node count and layer assignment
- [ ] 8.3 Add badge test: verify badge appears when orchestration data present, absent when None, correct color for each status
- [ ] 8.4 Add approve action test: mock orchestration-state.json, click approve, verify file written with approved=true
- [ ] 8.5 Add FeatureWorker orchestration polling test: create temp orchestration-state.json, verify parsed data structure, verify None for missing file, verify None for malformed JSON
