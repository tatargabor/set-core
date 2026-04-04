# Change: dashboard-unified-logs

## Why

The change detail panel has 3 tabs: Log, Timeline, Gates. Gate outputs (Build, Test, E2E, Review, Smoke) live under the Gates tab as collapsible sections, while Task sessions live under the Log tab. This splits related information — you want to see the agent's work AND the gate results in one place. Additionally, merge and archive events have no log representation at all.

## What Changes

### 1. Merge Gates tab into Log tab as sub-tabs

The Log tab gets a tab bar at the top of the right pane (where change session logs appear):
- **Task** (existing session tabs) — agent work sessions
- **Build** — gate build output
- **Test** — gate test output
- **E2E** — gate E2E output
- **Review** — gate review output
- **Smoke** — gate smoke output
- **Merge** — merge event log (from orchestration events)

Each gate sub-tab shows the same content as the current GateDetail section (result badge + output text), but as a full-pane log view instead of collapsed accordion.

### 2. Remove Gates tab

With gate outputs now in the Log tab, the Gates tab becomes redundant. Remove it — 2 tabs (Log, Timeline) instead of 3.

### 3. Add Merge/Archive event logs

Extract merge and archive events from the orchestration log or state extras and display them as sub-tabs in the Log tab.

## Capabilities

### New Capabilities
- `dashboard-unified-logs` — unified log view with gate/merge/archive sub-tabs

## Impact

- `web/src/pages/Dashboard.tsx` — remove Gates tab, Log tab only
- `web/src/components/LogPanel.tsx` — add sub-tab bar for Task/Build/Test/E2E/Review/Smoke/Merge
- `web/src/components/GateDetail.tsx` — may be removed or refactored into LogPanel
