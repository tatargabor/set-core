# Tasks: add-change-state-dag

## 1. Dependency + scaffolding

**Goal:** add `@xyflow/react`, wire up the lazy-loaded component entry point, and create the dag/ subdirectory layout without touching any existing components.

- [x] 1.1 Add `@xyflow/react` to `web/package.json` as a pinned caret version (`^12.3.0` or the latest stable 12.x at implementation time). Run `pnpm install` from `web/` and commit the lockfile update [REQ: lazy-loaded-react-flow-bundle]
- [x] 1.2 Create directory `web/src/components/dag/` for the new node components and `web/src/lib/dag/` for the transform, layout, and types [REQ: dag-panel-entry-point]
- [x] 1.3 Create `web/src/lib/dag/types.ts` with the `GateKind`, `GateResult`, `AttemptNode`, `Attempt`, and `AttemptGraph` type definitions exactly as specified in design.md §Data Contract [REQ: journal-to-graph-transform]
- [x] 1.4 Create an empty `web/src/components/ChangeDagPanel.tsx` file exporting a default no-op React component so the lazy import resolves during early wiring. Real content lands in section 4 [REQ: dag-panel-entry-point]
- [x] 1.5 Wire the lazy import at the mount site in `web/src/pages/Dashboard.tsx` (or wherever the expanded-change area lives — confirm with `grep -rn ChangeTimelineDetail web/src/pages`) via `const ChangeDagPanel = React.lazy(() => import('../components/ChangeDagPanel'))`. Wrap the mount in `<Suspense fallback={<div>Loading DAG...</div>}>` [REQ: lazy-loaded-react-flow-bundle]
- [x] 1.6 Verify the lazy chunk is generated: run `pnpm build` from `web/` and confirm a new chunk containing `ChangeDagPanel` appears in `web/dist/assets/` [REQ: lazy-loaded-react-flow-bundle]

## 2. Journal-to-graph transform (pure, unit-tested)

**Goal:** implement `journalToAttemptGraph` as a pure function with full unit-test coverage. No React, no React Flow imports in this file.

- [x] 2.1 Create `web/src/lib/dag/journalToAttemptGraph.ts` with the signature `journalToAttemptGraph(entries: JournalEntry[], verdictSidecars?: VerdictSidecar[]): AttemptGraph`. Import `JournalEntry` from the existing `web/src/lib/api.ts` (the type is defined by the `change-journal` capability from `add-state-archive-system`) [REQ: journal-to-graph-transform]
- [x] 2.2 Implement stable `ts`-primary, `seq`-tiebreaker sort at the top of the function. Do NOT assume the input is already sorted — the API sorts but tests may pass unsorted input [REQ: journal-to-graph-transform]
- [x] 2.3 Implement the attempt-splitting loop: walk entries in order, open a new `Attempt` whenever `current_step` transitions to `"implement"` after any `*_result` entries have been seen in the current attempt. First attempt starts at the first entry [REQ: journal-to-graph-transform]
- [x] 2.4 For each gate-result entry (`build_result`, `test_result`, `e2e_result`, `review_result`, `smoke_result`, `scope_check_result`, `rules_result`, `e2e_coverage_result`, `merge_result`), create an `AttemptNode` with the right `kind`, copy the `ts` as `startedAt`, and track the cross-attempt `runIndexForKind` via a counter keyed by kind [REQ: gate-node-rendering]
- [x] 2.5 Attach `ms` and `output` to each `AttemptNode` by looking at neighboring `gate_<kind>_ms` and `<kind>_output` entries within a ±2s window, mirroring the logic in `lib/set_orch/api/orchestration.py::_pick_closest` [REQ: journal-to-graph-transform]
- [x] 2.6 For gate-result entries with value `'skip'`, do NOT create a node. Skipped gates are invisible [REQ: journal-to-graph-transform]
- [x] 2.7 When encountering a `status: merged` entry, mark the current attempt `outcome: 'merged'` and set `graph.terminal = 'merged'`. When encountering `status: failed`, set `outcome: 'failed'` and `graph.terminal = 'failed'` [REQ: journal-to-graph-transform]
- [x] 2.8 When an attempt closes on retry (new `current_step: implement`), compute `retryReason`: if the last node is a `merge` with fail result → `'merge-conflict'`, else if any gate failed → `'gate-fail'`, else → `'unknown'` [REQ: journal-to-graph-transform]
- [x] 2.9 When the last attempt has no terminal status and its last node has no `result`, set that node's `result` to `'running'` and set `graph.terminal = 'in-progress'` [REQ: journal-to-graph-transform]
- [x] 2.10 Prepend an `ImplNode` to each attempt's `nodes` array with duration = time between the attempt's `current_step: implement` and its first gate-result entry. If the attempt has zero gate entries, duration = `now - started` [REQ: impl-node-rendering]
- [x] 2.11 When `verdictSidecars` is provided, enrich matching nodes with `verdictSource` and `downgrades`. For now the argument is optional and can be empty — full wiring lands in iteration 2 [REQ: gate-node-rendering]
- [x] 2.12 Create `web/tests/unit/journalToAttemptGraph.test.ts` (Vitest). Add cases: (a) empty input, (b) single-attempt happy path, (c) two-attempt with test-fail retry, (d) three-attempt with mixed gate fails, (e) merge-conflict retry, (f) interrupted attempt, (g) skipped gate, (h) out-of-order seqs with same ts, (i) impl duration calculation, (j) runIndexForKind increments across attempts [REQ: journal-to-graph-transform]
- [x] 2.13 Run `pnpm test:unit` from `web/` and confirm all cases pass. Fix any failures by updating the transform (tests are the spec) [REQ: journal-to-graph-transform]

## 3. Fixed-grid layout function (pure, unit-tested)

**Goal:** implement `layoutAttemptGraph` as a pure function that produces React Flow–compatible node and edge arrays.

- [x] 3.1 Create `web/src/lib/dag/layout.ts` with a `LayoutConstants` interface and the default values from design.md §Layout Function (nodeWidth=150, nodeHeight=60, columnGap=30, rowHeight=90, attemptGap=20, leftMargin=20, topMargin=20) [REQ: fixed-grid-layout-function]
- [x] 3.2 Implement `layoutAttemptGraph(graph, constants?)` returning `{ nodes: Node[], edges: Edge[] }`. Import `Node` and `Edge` types from `@xyflow/react` [REQ: fixed-grid-layout-function]
- [x] 3.3 For each attempt `k` in order, iterate its nodes in order. Emit one React Flow `Node` per `AttemptNode` with `position: { x: leftMargin + j * (nodeWidth + columnGap), y: topMargin + (k-1) * (rowHeight + attemptGap) }` [REQ: fixed-grid-layout-function]
- [x] 3.4 Set the React Flow `type` field to `'gate'`, `'impl'`, or `'terminal'` based on `AttemptNode.kind`. Pass the original `AttemptNode` as the React Flow node's `data` field [REQ: gate-node-rendering]
- [x] 3.5 Emit happy edges of `type: 'default'` between each pair of adjacent nodes within the same attempt. Use neutral-500 stroke color and 1.5px width via the `style` prop [REQ: fixed-grid-layout-function]
- [x] 3.6 Emit retry edges of `type: 'smoothstep'` between the last node of each non-terminal attempt and the first node of the next attempt. Set `sourceHandle: 'bottom'`, `targetHandle: 'top'`, color based on `retryReason` (amber for gate-fail, orange for merge-conflict, violet for replan, neutral for unknown) [REQ: fixed-grid-layout-function]
- [x] 3.7 When the graph's `terminal` is `'merged'` or `'failed'`, append a `TerminalNode` to the last attempt's row at `x` after the last real node. Emit one happy edge from the final gate to the terminal [REQ: terminal-node-rendering]
- [x] 3.8 Create `web/tests/unit/layout.test.ts`. Cases: (a) one attempt with 3 gates → 4 nodes (impl + 3 gates) at expected x positions, (b) 3 attempts → y positions stack correctly, (c) retry edge source/target handle positions, (d) merged graph adds terminal node, (e) in-progress graph has no terminal, (f) custom constants override defaults [REQ: fixed-grid-layout-function]
- [x] 3.9 Run unit tests and confirm all layout cases pass [REQ: fixed-grid-layout-function]

## 4. Custom React Flow node components

**Goal:** implement the three custom node types with Tailwind classes and compact/expanded variants.

- [x] 4.1 Create `web/src/components/dag/GateNode.tsx`. The component receives `NodeProps<AttemptNode>` from `@xyflow/react` and renders the compact card at 150×60px. Use Tailwind classes consistent with the existing `ChangeTimelineDetail` palette (`bg-neutral-900/50`, `border`, color by result) [REQ: gate-node-rendering]
- [x] 4.2 In `GateNode`, map `result` to icon and color: `pass → ✓ green-400`, `fail → ✗ red-400`, `warn → ⚠ amber-400`, `skip → – neutral-500` (should not render, but defensive), `running → ● blue-400 animate-pulse`, `null → ○ neutral-600` [REQ: gate-node-rendering]
- [x] 4.3 In `GateNode`, render the `⟳N` badge (top-right corner) only when `runIndexForKind > 1`. Render the `⚖` icon when the node has a non-empty `downgrades` array or `verdictSource === 'classifier_downgrade'` [REQ: gate-node-rendering]
- [x] 4.4 In `GateNode`, implement the hover-expand behavior via a `useState` boolean and CSS transitions. When `hovered`, the node grows to ~260×140px and reveals attempt number, started-at time (formatted `HH:mm:ss`), and verdict source. Add `transition-all duration-150` [REQ: gate-node-rendering]
- [x] 4.5 In `GateNode`, add a `Handle` from `@xyflow/react` on the left (`type: 'target'`, `position: Position.Left`) and right (`type: 'source'`, `position: Position.Right`). Add a bottom source handle for retry edges [REQ: gate-node-rendering]
- [x] 4.6 Create `web/src/components/dag/ImplNode.tsx`. Same structure as `GateNode` but with a `✎` icon, a blue/violet accent border (`border-violet-500/40`), and a "#N" attempt badge. The label is `impl #N` where N is the attempt number [REQ: impl-node-rendering]
- [x] 4.7 Create `web/src/components/dag/TerminalNode.tsx`. Two visual variants: merged (green pill, large `✓`, label `MERGED ✓`, subtitle shows attempt number and total duration) and failed (red pill, large `✗`, label `FAILED ✗`, subtitle shows failure reason if available). The node has a left target handle only [REQ: terminal-node-rendering]
- [x] 4.8 Wire all three node components as `nodeTypes` in the React Flow instance in `ChangeDagPanel`: `{ gate: GateNode, impl: ImplNode, terminal: TerminalNode }`. Pass as a memoized object to avoid React Flow re-registration warnings [REQ: dag-panel-entry-point]

## 5. Panel, toolbar, and detail panel

**Goal:** wire the panel entry point, toolbar, and detail panel. This is the component that glues transform + layout + custom nodes together and handles polling.

- [x] 5.1 Replace the stub in `web/src/components/ChangeDagPanel.tsx` with the real component. It receives `project: string` and `changeName: string` as props. It holds state for `journal`, `error`, `loading`, `selectedNodeId`, and `viewMode` ('dag' | 'linear') [REQ: dag-panel-entry-point]
- [x] 5.2 In `ChangeDagPanel`, implement the poll effect: fetch `/journal` on mount, re-fetch every 10 seconds via `setInterval`, clear on unmount. Use the existing `getChangeJournal(project, name)` fetcher from `web/src/lib/api.ts` (already added by `add-state-archive-system`) [REQ: dag-panel-entry-point]
- [x] 5.3 Derive the `AttemptGraph` from the fetched journal via `journalToAttemptGraph(journal.entries)`. Memoize with `useMemo` keyed by `journal.entries` so re-renders don't re-transform [REQ: journal-to-graph-transform]
- [x] 5.4 Derive `{ nodes, edges }` from the graph via `layoutAttemptGraph(graph)`. Memoize with `useMemo` keyed by `graph` [REQ: fixed-grid-layout-function]
- [x] 5.5 Create `web/src/components/dag/DagToolbar.tsx`. Accept props: `attemptCount`, `totalDurationMs`, `totalGateRuns`, `viewMode`, `onViewModeChange`. Render a horizontal flex row with the counts on the left and a segmented toggle button on the right with two options: "DAG" and "Linear" [REQ: toolbar-with-dag-linear-view-toggle]
- [x] 5.6 In `ChangeDagPanel`, render `<DagToolbar>` above the React Flow canvas. Pass `graph.attempts.length`, `graph.totalMs`, `graph.totalGateRuns`, and the viewMode state [REQ: toolbar-with-dag-linear-view-toggle]
- [x] 5.7 When `viewMode === 'linear'`, render the existing `ChangeTimelineDetail` component instead of React Flow. Pass `project` and `changeName` props. Do NOT fetch twice — the DAG panel continues to poll the journal in the background so the toggle is instant [REQ: existing-views-coexist-unchanged]
- [x] 5.8 When `viewMode === 'dag'` and `graph.attempts.length > 0`, render a `<ReactFlow>` instance with `nodes`, `edges`, `nodeTypes`, `fitView`, `minZoom={0.3}`, `maxZoom={2}`, `nodesDraggable={false}`, `nodesConnectable={false}`, and `onNodeClick={(_, node) => setSelectedNodeId(prev => prev === node.id ? null : node.id)}` [REQ: dag-panel-entry-point]
- [x] 5.9 Inside `<ReactFlow>`, add `<Background variant="dots" gap={20} />`, `<MiniMap pannable zoomable />`, and `<Controls showInteractive={false} />` from `@xyflow/react`. Import the React Flow CSS via `import '@xyflow/react/dist/style.css'` at the top of the file [REQ: dag-panel-entry-point]
- [x] 5.10 Create `web/src/components/dag/DagDetailPanel.tsx`. Accept `node: AttemptNode | null` and `onClose: () => void`. Render an inline panel under the React Flow canvas (NOT a modal). Use `bg-neutral-900/70` and a border [REQ: detail-panel-on-node-click]
- [x] 5.11 In `DagDetailPanel`, render the gate name, attempt number, run index, started-at time, duration, and verdict source in a header row. Render the gate `output` in a `<pre>` block with max-height and scroll-y. Render the `downgrades` array as a small table when non-empty [REQ: detail-panel-on-node-click]
- [x] 5.12 In `DagDetailPanel`, add a close button in the top-right and handle the Escape key via a `useEffect` adding a document-level keydown listener [REQ: detail-panel-on-node-click]
- [x] 5.13 In `ChangeDagPanel`, wire the selected node from `selectedNodeId` back to its `AttemptNode` via a lookup on `graph.attempts[*].nodes`. Pass to `DagDetailPanel` [REQ: detail-panel-on-node-click]
- [x] 5.14 Handle the empty-state: when `graph.attempts.length === 0`, render an empty-state card with the message "No journal data for this change yet" and a button that sets `viewMode = 'linear'` [REQ: empty-state-handling]
- [x] 5.15 Handle the error state: when the fetch rejects with 404, show an error card with the change name. When it rejects with any other error, log to console and show a generic error card. The toolbar's Linear toggle remains functional in both error states [REQ: empty-state-handling]
- [x] 5.16 Handle transform failure: wrap the `journalToAttemptGraph` call in a try/catch. On throw, log `console.error` with the change name and raw entries, and show the empty-state card [REQ: empty-state-handling]

## 6. Integration with existing Changes tab

**Goal:** mount the panel in the existing expanded-change area without disturbing the row ribbon or the linear view.

- [x] 6.1 Identify the current mount point of `ChangeTimelineDetail` by searching `web/src/` for its usage. Confirm there is exactly one mount site and note the file path [REQ: existing-views-coexist-unchanged]
- [x] 6.2 At that mount site, replace the direct `<ChangeTimelineDetail>` usage with `<ChangeDagPanel>`. The DAG panel internally falls back to `ChangeTimelineDetail` when `viewMode === 'linear'`, so no functionality is lost [REQ: existing-views-coexist-unchanged]
- [x] 6.3 Verify the row ribbon (`ChangeTimeline` in `ChangeTable`) is untouched by the change — `git diff web/src/components/ChangeTable.tsx web/src/components/ChangeTimeline.tsx` should show zero changes [REQ: existing-views-coexist-unchanged]
- [x] 6.4 Start the dev server (`pnpm dev` from `web/`) and manually verify: (a) row ribbon looks identical, (b) expanding a change shows the DAG by default, (c) toggling to Linear shows the old session cards, (d) clicking a node opens the detail panel [REQ: dag-panel-entry-point]

## 7. E2E test coverage

**Goal:** add Playwright tests under `web/tests/e2e/` that validate the DAG end-to-end against a real project fixture.

- [x] 7.1 Create `web/tests/e2e/change-state-dag.spec.ts`. Follow the structure in `web/tests/e2e/README.md` — use `E2E_PROJECT` env var, no mocks [REQ: e2e-test-coverage]
- [x] 7.2 Test case 1: visit the Changes tab for a multi-attempt change, assert that N attempt rows are visible (where N matches the journal read from the API beforehand), and that the toolbar shows the same count [REQ: e2e-test-coverage]
- [x] 7.3 Test case 2: click on a gate node, assert the detail panel becomes visible with expected output text [REQ: e2e-test-coverage]
- [x] 7.4 Test case 3: click the Linear toggle, assert the React Flow canvas is no longer in the DOM and session cards from `ChangeTimelineDetail` are visible [REQ: e2e-test-coverage]
- [x] 7.5 Run the E2E suite from `web/` with `E2E_PROJECT=<a-multi-attempt-fixture-project> pnpm test:e2e`. Fix any failures. If no fixture project is available, document the required journal shape in a test README [REQ: e2e-test-coverage]

## 8. Final verification

**Goal:** verify all the spec scenarios, visual quality, and backwards compatibility before archiving.

- [x] 8.1 Run `pnpm build` from `web/`. Confirm the build succeeds and a lazy chunk containing `ChangeDagPanel` and `@xyflow/react` is produced separately from the main bundle [REQ: lazy-loaded-react-flow-bundle]
- [x] 8.2 Measure the main bundle size before and after by running `pnpm build` on main and on this branch, comparing `web/dist/assets/index-*.js` sizes. Confirm the delta is < 5 KB (the panel mount + lazy import plumbing) [REQ: lazy-loaded-react-flow-bundle]
- [x] 8.3 Visual QA against a completed multi-attempt change: open the dashboard, expand the change, verify the DAG matches what `cat <state_dir>/journals/<change>.jsonl` reports. Take a screenshot for the PR description [REQ: dag-panel-entry-point]
- [x] 8.4 Visual QA against a legacy change without a journal (if available): verify the empty-state card renders and the Linear toggle still works [REQ: empty-state-handling]
- [x] 8.5 Visual QA against an in-progress change: verify the last node shows a pulsing `●` indicator and the graph terminal is not rendered [REQ: terminal-node-rendering]
- [x] 8.6 Run `pnpm test:unit` and `pnpm test:e2e` both cleanly green [REQ: e2e-test-coverage]
- [x] 8.7 Run `openspec verify add-change-state-dag` to confirm all scenarios are covered and the implementation matches the specs
