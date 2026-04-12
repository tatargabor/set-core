# Tasks: activity-timeline

## 1. Event Instrumentation (fill gaps)

- [x] 1.1 Add IDLE_START/IDLE_END event emission in `lib/set_orch/watchdog.py` — emit IDLE_START when no watched change has activity for >60s, IDLE_END when activity resumes. Track idle state in watchdog state dict. [REQ: idle-detection-events]
- [x] 1.2 Add MANUAL_STOP event emission in `lib/set_orch/dispatcher.py:pause_change()` (line ~2362) [REQ: manual-stop-resume-events]
- [x] 1.3 Add MANUAL_RESUME event emission in `lib/set_orch/dispatcher.py:resume_change()` (line ~2395) [REQ: manual-stop-resume-events]
- [x] 1.4 Add WATCHDOG_ESCALATION event emission in `lib/set_orch/watchdog.py` when escalation_level increases — include from_level, to_level, action in event data [REQ: watchdog-escalation-events]
- [x] 1.5 Add ITERATION_START event emission in `lib/set_orch/loop_state.py:add_iteration()` (line ~153) — emit when a new iteration entry is created [REQ: iteration-boundary-events]
- [x] 1.6 Add ITERATION_END event emission in `lib/set_orch/loop_state.py` — emit when an iteration's `ended` field is set, include iteration number, duration_ms, tokens_used [REQ: iteration-boundary-events]
- [x] 1.7 Add CONFLICT_RESOLUTION_START/END events in `lib/set_orch/merger.py` around the conflict resolution logic (near `_clean_untracked_merge_conflicts` and rebase attempts) [REQ: conflict-resolution-events]

## 2. Backend: Activity Timeline Aggregator

- [x] 2.1 Create `lib/set_orch/api/activity.py` with the span reconstruction engine — parse orchestration-events JSONL, correlate start/end event pairs into typed spans [REQ: span-reconstruction-from-events]
- [x] 2.2 Implement multi-source event merging — read orchestration-events (+ rotated archives), sentinel events, and loop-state files; merge by timestamp into unified stream [REQ: multi-source-event-merging]
- [x] 2.3 Implement span builders for each category: gate spans (GATE_START→GATE_PASS), step spans (STEP_TRANSITION), merge spans (MERGE_START→MERGE_COMPLETE), idle spans (IDLE_START→IDLE_END or gap detection), stall-recovery spans (WATCHDOG_ESCALATION/sentinel crash→restart), dep-wait spans (STATE_CHANGE to=dep-blocked), manual-wait spans (MANUAL_STOP→MANUAL_RESUME) [REQ: span-reconstruction-from-events]
- [x] 2.4 Implement breakdown summary computation — aggregate span durations per category, calculate percentages, compute parallel_efficiency ratio [REQ: breakdown-summary]
- [x] 2.5 Register `GET /api/{project}/activity-timeline` endpoint with `from`, `to`, and `bucket_size` query parameters — wire to aggregator, return JSON response [REQ: activity-timeline-endpoint]
- [x] 2.6 Handle edge cases: no events, partial spans (open-ended), rotated archives, time range clipping [REQ: activity-timeline-endpoint]

## 3. Frontend: Activity Tab Registration

- [x] 3.1 Add `'activity'` to `PanelTab` union type in `web/src/pages/Dashboard.tsx` (line ~26) [REQ: activity-tab-registration]
- [x] 3.2 Add `{ id: 'activity', label: 'Activity' }` to tabs array in Dashboard.tsx (line ~206) [REQ: activity-tab-registration]
- [x] 3.3 Add conditional render for `activeTab === 'activity'` in Dashboard.tsx that renders `<ActivityView>` [REQ: activity-tab-registration]
- [x] 3.4 Add `'activity'` to the URL validation includes list in Dashboard.tsx (line ~50) [REQ: activity-tab-registration]

## 4. Frontend: API Client

- [x] 4.1 Add `ActivitySpan`, `ActivityBreakdown`, and `ActivityTimelineData` TypeScript types in `web/src/lib/api.ts` [REQ: activity-timeline-endpoint]
- [x] 4.2 Add `getActivityTimeline(project: string, from?: string, to?: string): Promise<ActivityTimelineData>` function in api.ts [REQ: activity-timeline-endpoint]

## 5. Frontend: ActivityView Component

- [x] 5.1 Create `web/src/components/ActivityView.tsx` — main component with summary header (wall time, activity time, parallel efficiency) [REQ: breakdown-summary]
- [x] 5.2 Implement Gantt timeline renderer — custom SVG with horizontal lanes per category, time axis on top, spans as colored rectangles. Category labels fixed on left. [REQ: gantt-timeline-visualization]
- [x] 5.3 Implement horizontal scroll — container with overflow-x-auto, category labels with sticky positioning [REQ: time-axis-zoom-and-scroll]
- [x] 5.4 Implement zoom in/out controls — adjust pixels-per-second ratio, re-render SVG width accordingly. Add zoom buttons and scroll-wheel-with-modifier support. [REQ: time-axis-zoom-and-scroll]
- [x] 5.5 Implement parallel span intensity — when multiple spans overlap on the same lane, increase opacity/shade and show "xN" indicator [REQ: gantt-timeline-visualization]
- [x] 5.6 Implement gate retry visualization — multiple blocks on same lane with pass/fail markers (checkmark/cross) [REQ: gantt-timeline-visualization]
- [x] 5.7 Hide empty lanes — filter out categories with no spans in the visible time range [REQ: gantt-timeline-visualization]
- [x] 5.8 Implement hover tooltip — show category, change name, start/end time, duration, result on span hover [REQ: hover-tooltip]
- [x] 5.9 Implement breakdown summary section — horizontal bars sorted by time, showing category name, duration, percentage. Use terminal/text visual style. [REQ: breakdown-summary]
- [x] 5.10 Implement auto-refresh (30s interval when orchestration is running) and manual refresh button with last-refresh timestamp [REQ: data-refresh]
- [x] 5.11 Auto-scroll to "now" on initial load during live runs [REQ: data-refresh]

## 6. Styling and Polish

- [x] 6.1 Define color palette for activity categories — use consistent, distinguishable colors in terminal/monospace aesthetic (match existing dashboard style: neutral-950 bg, etc.) [REQ: gantt-timeline-visualization]
- [x] 6.2 Ensure the Gantt timeline works at different zoom levels without visual artifacts [REQ: time-axis-zoom-and-scroll]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN client requests GET /api/{project}/activity-timeline THEN response includes wall_time_ms, activity_time_ms, parallel_efficiency, spans, breakdown [REQ: activity-timeline-endpoint, scenario: basic-timeline-request]
- [x] AC-2: WHEN client requests with from/to params THEN only overlapping spans are included, clipped to range [REQ: activity-timeline-endpoint, scenario: time-range-filtering]
- [x] AC-3: WHEN no events exist THEN response returns zeroed structure with empty arrays [REQ: activity-timeline-endpoint, scenario: no-events-exist]
- [x] AC-4: WHEN GATE_START and GATE_PASS exist for same gate/change THEN a gate span is produced [REQ: span-reconstruction-from-events, scenario: gate-span-from-gate-start-and-gate-pass]
- [x] AC-5: WHEN STEP_TRANSITION events mark implementing→fixing THEN an implementing span is produced [REQ: span-reconstruction-from-events, scenario: step-based-span-from-step-transition]
- [x] AC-6: WHEN no activity for >60s THEN an idle span is produced [REQ: span-reconstruction-from-events, scenario: idle-span-from-gap-detection]
- [x] AC-7: WHEN gate retries THEN each attempt is a separate span with retry number and result [REQ: span-reconstruction-from-events, scenario: gate-retry-produces-multiple-spans]
- [x] AC-8: WHEN two implementing spans overlap THEN breakdown sums both and activity_time > wall_time [REQ: breakdown-summary, scenario: parallel-spans-counted-independently]
- [x] AC-9: WHEN dashboard loads THEN Activity tab appears and is selectable [REQ: activity-tab-registration, scenario: tab-appears-in-tab-bar]
- [x] AC-10: WHEN spans exist for multiple categories THEN each gets its own swim lane with colored blocks [REQ: gantt-timeline-visualization, scenario: swim-lane-rendering]
- [x] AC-11: WHEN user zooms in THEN time detail increases; zoom out shows more time [REQ: time-axis-zoom-and-scroll, scenario: zoom-in]
- [x] AC-12: WHEN user hovers a span THEN tooltip shows category, change, time range, duration, result [REQ: hover-tooltip, scenario: tooltip-content]
- [x] AC-13: WHEN orchestration is running THEN data auto-refreshes every 30s [REQ: data-refresh, scenario: auto-refresh-during-live-run]
- [x] AC-14: WHEN watchdog detects no activity >60s THEN IDLE_START is emitted; on resume IDLE_END [REQ: idle-detection-events, scenario: idle-period-detected]
- [x] AC-15: WHEN pause_change() called THEN MANUAL_STOP event emitted [REQ: manual-stop-resume-events, scenario: user-pauses-a-change]
- [x] AC-16: WHEN watchdog escalates THEN WATCHDOG_ESCALATION event emitted with levels and action [REQ: watchdog-escalation-events, scenario: escalation-level-increases]
- [x] AC-17: WHEN iteration starts/ends THEN ITERATION_START/END events emitted with iteration number [REQ: iteration-boundary-events, scenario: iteration-starts]
- [x] AC-18: WHEN merger detects conflicts THEN CONFLICT_RESOLUTION_START/END events emitted [REQ: conflict-resolution-events, scenario: conflict-resolution-begins]
