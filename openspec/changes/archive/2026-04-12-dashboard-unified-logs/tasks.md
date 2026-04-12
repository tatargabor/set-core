# Tasks: dashboard-unified-logs

## 1. LogPanel sub-tab bar

- [x] 1.1 Add sub-tab state to LogPanel — `activeSubTab: 'task' | 'build' | 'test' | 'e2e' | 'review' | 'smoke' | 'merge'`, default `'task'`. Build dynamic tab list from `selectedChange` gate results. [REQ: gate-outputs-as-log-sub-tabs]
- [x] 1.2 Render sub-tab bar above the right pane content in LogPanel — small pill buttons matching existing session tab styling. Only show tabs for gates with results + always show Task. [REQ: gate-outputs-as-log-sub-tabs]
- [x] 1.3 When a gate sub-tab is active, render gate output pane: result badge (colored pass/fail/skip), execution time in ms, and full output in scrollable monospace pre block. Reuse styling from GateDetail. [REQ: gate-outputs-as-log-sub-tabs]
- [x] 1.4 Auto-select first failing gate sub-tab when change is selected (if any gate has result=fail). Otherwise default to Task. [REQ: task-sub-tab-is-default]

## 2. Merge sub-tab

- [x] 2.1 Add Merge sub-tab — appears only when change status is "merged". Content: filter orchestration log lines (`orchLines` prop) for lines containing the change name AND merge/archive keywords (MERGE, ARCHIVE, merge-queue, merged). [REQ: merge-event-log-sub-tab]

## 3. Remove Gates tab

- [x] 3.1 Remove `'gates'` from the tab bar in Dashboard.tsx — change `(['log', 'timeline', 'gates'] as const)` to `(['log', 'timeline'] as const)`. Remove the GateDetail render branch. [REQ: remove-standalone-gates-tab]
- [x] 3.2 Clean up: remove GateDetail import from Dashboard.tsx if no longer used elsewhere. Keep the GateDetail.tsx file for now (other pages may reference it). [REQ: remove-standalone-gates-tab]

## 4. Build and verify

- [x] 4.1 Run `cd web && pnpm build` to verify no TypeScript errors. [REQ: gate-outputs-as-log-sub-tabs]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN change has build_result/test_result/e2e_result THEN corresponding sub-tabs appear in Log right pane [REQ: gate-outputs-as-log-sub-tabs, scenario: change-with-gate-results]
- [x] AC-2: WHEN change has no gate results THEN only Task sub-tab shown [REQ: gate-outputs-as-log-sub-tabs, scenario: change-with-no-gate-results]
- [x] AC-3: WHEN user clicks gate sub-tab THEN shows result badge, time, scrollable output [REQ: gate-outputs-as-log-sub-tabs, scenario: gate-sub-tab-content-format]
- [x] AC-4: WHEN detail panel renders THEN tab bar shows Log and Timeline only (no Gates) [REQ: remove-standalone-gates-tab, scenario: tab-bar-after-change]
- [x] AC-5: WHEN change is merged THEN Merge sub-tab appears with filtered log lines [REQ: merge-event-log-sub-tab, scenario: change-with-merge-events]
- [x] AC-6: WHEN change not merged THEN no Merge sub-tab [REQ: merge-event-log-sub-tab, scenario: change-not-yet-merged]
- [x] AC-7: WHEN change selected with no failures THEN Task sub-tab default [REQ: task-sub-tab-is-default, scenario: default-selection-no-failures]
- [x] AC-8: WHEN change selected with failing gate THEN failing gate sub-tab auto-selected [REQ: task-sub-tab-is-default, scenario: default-selection-gate-failure]
