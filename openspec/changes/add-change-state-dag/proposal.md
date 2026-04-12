# Proposal: Change State DAG — per-change 2D flow visualization

## Why

The web dashboard's Changes tab currently shows two flat views of a change's lifecycle: (1) an inline horizontal "gate ribbon" in the table rows (`ChangeTimeline`) that collapses the whole history into one strip of final-result colors, and (2) an expanded vertical session list (`ChangeTimelineDetail`) that stacks session cards top-to-bottom. Neither of these makes it possible to answer, at a glance, the question a user actually has when looking at a completed or stuck change: **"which gates retried, how many times, and in what order did the attempts actually unfold?"**

The concrete pain points:

1. **Retry topology is invisible.** A change that merged on attempt 4 after three retries looks, in the horizontal ribbon, identical to a change that merged on attempt 1. Only the last result is shown. A user has to expand the detail pane, scroll through session cards, and mentally reconstruct the flow.
2. **Gate re-runs are hidden.** When `test` runs three times across three attempts, the user sees three disconnected `Test ✓` cells in three different session cards — the cross-attempt pattern ("test keeps flaking") does not emerge visually.
3. **Classifier downgrades are buried in verdict sidecars.** The new `gate_verdict.py` tracks `classifier_downgrade` as a `source`, with per-finding `downgrades` in the sidecar. Users currently have no way to see this in the dashboard.
4. **Merge-conflict retries look the same as gate-fail retries.** From the session card list, a retry triggered by an e2e gate failure is visually indistinguishable from a retry triggered by a merge conflict, even though the root cause and the next debugging step are completely different.
5. **Session cards scroll forever on high-retry changes.** A change that retries 6+ times forces the user to scroll a long vertical list, losing the ability to compare gate durations across attempts side-by-side.

The `add-state-archive-system` change already landed the data primitive that makes a richer visualization possible: the per-change journal (`<state_dir>/journals/<change>.jsonl`) is append-only, `seq`-ordered, and captures every state.json field overwrite that matters (gate results, gate outputs, gate timings, `status`, `current_step`, `retry_context`). The `GET /api/{project}/changes/{name}/journal` endpoint already exposes both raw entries and a per-gate grouped view. The data is there. Nothing in the current dashboard renders it as a flow.

This change adds a **Change State DAG**: a 2D node-and-edge graph rendered with React Flow, where each node is one concrete gate run (not an abstract state), each row is one attempt, and edges show happy-path progression horizontally and retry/conflict loops vertically. The visualization is derived from the same journal endpoint the gate-history sub-tabs use, so it adds zero backend surface area beyond a thin journal-to-graph transform that lives in the frontend.

## What Changes

### Web — new Change State DAG panel
- **ADD** a new React component `ChangeDagPanel` that fetches `/changes/{name}/journal`, transforms the journal into an `AttemptGraph` structure, and renders it with React Flow.
- **ADD** a pure, unit-testable `journalToAttemptGraph()` transform function in `web/src/lib/dag/` that splits the raw journal into `Attempt[]`, each containing ordered `AttemptNode[]` for impl + gates + terminal.
- **ADD** three custom React Flow node types: `GateNode` (for gate runs — build, test, e2e, review, smoke, scope_check, rules, e2e_coverage, merge), `ImplNode` (for the implementing phase), and `TerminalNode` (for merged / failed / in-progress end states).
- **ADD** `@xyflow/react` as a dependency, lazy-loaded from the DAG panel entry point so the main bundle is unaffected.
- **ADD** compact and expanded node variants: compact (150×60px) shows result icon, gate name, run badge, duration; expanded (on hover/selection, 260×140px) adds attempt number, started-at time, verdict source, and an optional gate output snippet.
- **ADD** a `DagDetailPanel` that opens under the graph when a node is selected and shows the full gate output, the downgrade audit trail (when present), and any linked issue IDs.
- **ADD** a toolbar above the graph with attempt count, total duration, total gate-run count, and a "Linear view" toggle that switches back to the existing `ChangeTimelineDetail`.
- **ADD** Playwright E2E test coverage: one test asserts the DAG renders with the correct number of attempts and nodes for a seeded project, one test asserts the click-to-select opens the detail panel, one test asserts the Linear view toggle switches components.

### Web — keep the existing two views
- **KEEP** the `ChangeTimeline` gate ribbon inline in `ChangeTable` rows unchanged — the DAG is only shown in the expanded/detail area.
- **KEEP** `ChangeTimelineDetail` as the fallback "linear view" that the toolbar toggle switches to. Both views read the same journal data so they cannot diverge.
- **KEEP** the `LogPanel` gate-history sub-tabs (from `gate-history-view`) unchanged — the DAG and the sub-tabs answer different questions and should coexist.

### Web — backwards compatibility
- **KEEP** legacy changes without a journal working: if `/journal` returns an empty response, the DAG shows an empty-state message and the toolbar's linear-view toggle pre-selects the linear view.

## Capabilities

### New Capabilities
- `change-state-dag` — web dashboard renders a 2D node-and-edge flow graph of a change's actual trajectory through gates, attempts, and retries, derived from the journal API.

### Modified Capabilities
None. This change is additive. The existing `change-journal` capability (owned by `add-state-archive-system`) provides the data source unchanged. The existing `gate-history-view` capability continues to own the LogPanel sub-tab rendering. The `ChangeTimeline` row ribbon and `ChangeTimelineDetail` linear panel are both kept.

## Impact

**Code affected — web frontend:**
- `web/src/components/ChangeDagPanel.tsx` — NEW component, entry point for the DAG visualization.
- `web/src/components/dag/GateNode.tsx` — NEW custom React Flow node for gate runs.
- `web/src/components/dag/ImplNode.tsx` — NEW custom React Flow node for impl phases.
- `web/src/components/dag/TerminalNode.tsx` — NEW custom React Flow node for merged/failed/in-progress.
- `web/src/components/dag/DagDetailPanel.tsx` — NEW click-to-select detail viewer.
- `web/src/components/dag/DagToolbar.tsx` — NEW toolbar with counts and linear-view toggle.
- `web/src/lib/dag/journalToAttemptGraph.ts` — NEW pure transform, unit-tested.
- `web/src/lib/dag/layout.ts` — NEW fixed-grid layout math (attempt rows × gate columns).
- `web/src/lib/dag/types.ts` — NEW `AttemptGraph`, `Attempt`, `AttemptNode` types.
- `web/src/lib/api.ts` — reuse existing `getChangeJournal` (from `add-state-archive-system`); no new fetcher needed.
- `web/src/pages/Dashboard.tsx` or wherever the expanded change panel is rendered — mount `ChangeDagPanel` inside the expanded area.
- `web/package.json` — ADD `@xyflow/react` dependency.
- `web/tests/e2e/change-state-dag.spec.ts` — NEW Playwright test file.
- `web/tests/unit/journalToAttemptGraph.test.ts` — NEW unit test file for the transform.

**Code affected — backend:**
- None. The `GET /api/{project}/changes/{name}/journal` endpoint already exists.

**Data storage:**
- None. The DAG reads the existing per-change journal.

**Performance:**
- Bundle: `@xyflow/react` is ~40 KB gzipped; lazy-loaded so the initial Changes-tab load is unaffected. The DAG panel only loads when a user expands a change.
- Polling: reuses the existing 10-second poll on the journal endpoint. No new network traffic.
- Render: a 4-attempt change has ~30 nodes; React Flow handles this with no perceptible cost. High-retry changes (10+ attempts, 70+ nodes) rely on React Flow's built-in pan/zoom.

**Risks:**
- `@xyflow/react` is a new dependency surface. Mitigated by lazy-loading and by the fact that React Flow has stable 12.x releases under MIT license.
- Journal-to-graph transform has edge cases (interrupted gate runs, skipped gates, parallel attempts). Mitigated by unit tests covering each case and by a "fallback to linear view" path when the transform fails to produce a valid graph.
- Visual clutter on changes with many retries. Mitigated by the compact node default (only expands on hover), the fit-view-on-load behavior, and the always-available linear view toggle.
