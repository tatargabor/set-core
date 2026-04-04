# Design: dashboard-unified-logs

## Context

The Log tab's right pane already has a tab bar for task sessions (Session 1, Session 2, etc.). Gate outputs are in a separate Gates tab as collapsible accordions. The user wants all logs in one place.

## Goals / Non-Goals

**Goals:**
- Gate outputs appear as sub-tabs alongside Task sessions in the Log tab
- Merge/archive events visible as log entries
- Remove the standalone Gates tab

**Non-Goals:**
- Changing the Timeline tab
- Changing the left pane (orchestration log)
- Adding new API endpoints (use existing data from ChangeInfo)

## Decisions

### D1: Sub-tab bar above the right pane content

**Choice:** A two-level tab structure:
- Level 1 (existing): Log | Timeline
- Level 2 (inside Log, right pane): Task | Build | Test | E2E | Review | Smoke | Merge

The sub-tabs only appear when a change is selected. Task shows the existing session picker + log. Gate sub-tabs show result badge + full output. Merge shows merge event details.

**Why:** Minimal UI change — the session tab bar already exists, we just add gate tabs to it. No new components needed, just extending LogPanel.

### D2: Gate sub-tabs show result + output inline

**Choice:** Each gate sub-tab shows: status badge (pass/fail/skip) + timing + full output text in the same scrollable pane format as task sessions.

**Why:** Consistent with how task sessions look. No need for accordion expand/collapse — each tab is one gate, always fully visible.

### D3: Only show sub-tabs for gates with results

**Choice:** Sub-tabs are dynamically generated — only gates that have a result appear. Task tab is always present.

**Why:** Avoids empty tabs. A change with no E2E gate won't show an E2E tab.

### D4: Merge tab shows orchestration events

**Choice:** Extract merge-related lines from the orchestration log (MERGE_START, MERGE_SUCCESS, MERGE_FAIL, ARCHIVE events) filtered to the selected change.

**Why:** No new API needed — orchestration log already contains these events. Just filter by change name.
