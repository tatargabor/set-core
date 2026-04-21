# Design: Change State DAG

## Context

The web dashboard is a Vite + React 18 + Tailwind app under `web/`. The Changes tab currently renders a `ChangeTable` where each row shows a change with an inline `ChangeTimeline` gate ribbon. When a user expands a row, `ChangeTimelineDetail` renders a vertical list of session cards derived from `getChangeTimeline(project, name)`, an API that returns per-session tokens, gates, and timings.

Two things changed recently that make a richer visualization both possible and valuable:

1. **Per-change journal.** The `change-journal` capability (from `add-state-archive-system`) added an append-only JSONL file at `<state_dir>/journals/<change>.jsonl` and a `GET /api/{project}/changes/{name}/journal` endpoint that returns raw entries plus a pre-grouped per-gate `run` list. Every gate-run mutation is captured with a `seq`, a `ts`, and `old`/`new` values.
2. **Classifier downgrade audit trail.** The `review-severity-calibration` capability added a `downgrades: list[dict]` field on `GateVerdict` and a `classifier_downgrade` source tag, which together track when the LLM verdict classifier lowered a reviewer-tagged severity. This information is not currently visible in the dashboard anywhere.

The Change State DAG is a new React component that turns the journal + verdict-sidecar data into a 2D graph where users can see the actual, physical trajectory a change took through the gate pipeline — including retries, classifier interventions, and merge conflicts — at a glance.

### Why React Flow (and not custom SVG or D3)

The space of options considered:
- **Custom SVG from scratch.** Maximum control, zero dependency. Rejected because we would reinvent pan/zoom, minimap, edge routing, and custom node rendering.
- **D3 directly.** Powerful, small footprint. Rejected because D3's imperative API fights React's declarative model; state sync between React props and D3 selections is a known source of bugs.
- **Visx.** React-friendly D3 primitives. Viable but requires hand-rolling node drag/zoom/pan/minimap components. More code than React Flow for the same visual result.
- **Cytoscape.js.** Graph theory focus, heavier footprint (~200 KB). Overkill — we have a simple directed graph with a fixed layout and don't need graph algorithms.
- **Mermaid.** Declarative, zero-interaction. Rejected because it renders static SVG with no click-to-select or hover affordances.
- **@xyflow/react (React Flow 12).** React-native, ~40 KB gzipped, MIT, active maintenance, built-in pan/zoom/minimap/controls, custom node rendering via React components, smoothstep edges that handle retry loop-backs naturally, stable fitView API.

React Flow is the right tradeoff. It gives us everything we need (pan/zoom, minimap, custom nodes, smoothstep retry edges) and nothing we don't (layout algorithms, graph analysis). Lazy-loading keeps the dep off the main bundle.

### Why canonical state-machine view was rejected as the default

An earlier draft proposed a canonical state-machine DAG: fixed topology (pending → implementing → verifying → build → test → ...) with the change's actual path highlighted as a colored line on top. Two views were considered:

- **Canonical (fixed topology, highlighted path).** Every change looks the same; retries become self-loops with traversal counts. Teaches the state machine's structure. Rejected as the default because it answers "what is the state machine" rather than "what did this particular change actually do" — the latter is the question users actually have when debugging or reviewing a change.
- **Unrolled (one node per gate run, one row per attempt).** Every run gets its own node; retries pull the graph down to a new row. Every change has its own shape. Accepted as the default because it directly answers the "what did this change do" question and surfaces retry patterns that canonical view compresses away.

The canonical view is **not** shipped in this change. It remains a possible future toggle if users ask for it, but YAGNI for now.

## Goals / Non-Goals

**Goals:**
- Render a 2D graph of a change's actual journey through the gate pipeline, one node per gate run, one row per attempt.
- Make retry topology visible at a glance: number of attempts, which gates retried, which attempt succeeded, how merge conflicts differ from gate failures.
- Expose classifier downgrades (the `⚖` audit trail) so users can see when severity calibration intervened.
- Support click-to-inspect: selecting a node opens a detail panel with the full gate output.
- Coexist with the existing `ChangeTimeline` gate ribbon (inline in the table) and `ChangeTimelineDetail` linear session list (fallback view).
- Keep the backend surface area zero — reuse the existing journal endpoint.
- Make the journal-to-graph transform a pure, unit-testable function so edge cases can be covered without a browser.

**Non-Goals:**
- A canonical state-machine visualization. (Considered and rejected — see Context.)
- Real-time animated playback of the change's history. (Possible future addition; out of scope.)
- Multi-change overlay or comparison views. (Possible future; out of scope.)
- Edge-case issue/finding integration beyond showing linked issue IDs in the detail panel. (The issue system has its own registry; deep integration is out of scope.)
- Changing, extending, or refactoring the journal endpoint, the `change-journal` capability, or the `gate_verdict` sidecar format.
- Adding a new polling mechanism or SSE stream. The existing 10-second poll is reused.
- Replacing `ChangeTimelineDetail`. It remains available as the "linear view" toggle.

## Decisions

### Decision 1: Node model — one node per gate run, not per gate category

Every row in `journal.grouped.<gate>` becomes its own `AttemptNode`. If `test` ran three times, there are three `test` nodes, not one node with a `runs: 3` counter.

**Rationale:** the whole point of the DAG is to show the temporal sequence of runs. Collapsing re-runs into a single node with a counter is exactly what the existing `ChangeTimeline` gate ribbon already does — duplicating that information is not the goal.

**Implication:** the layout math lays out nodes on a grid where X = gate column order and Y = attempt row. Multiple attempts are multiple rows.

**Alternatives considered:**
- **One node per gate category, with a counter.** Rejected — that is the existing `ChangeTimeline`.
- **Hybrid: one node per category with an expandable "runs" drawer.** Rejected as overly complex; the row layout already gives a clean side-by-side comparison.

### Decision 2: Attempt splitting — current_step=implement marks a new attempt

The `journalToAttemptGraph` transform walks the raw entries in `(ts, seq)` order and opens a new `Attempt` whenever `current_step` transitions to `"implement"` after any gate-result entries have already been seen in the current attempt. The first attempt starts at the first entry with `current_step != null` or the first `*_result` entry.

A terminal `status: merged` or `status: failed` closes the final attempt and sets the `terminal` field on the `AttemptGraph`.

**Rationale:** `current_step` is the canonical source for "which phase is the engine currently running", and a transition back to `implement` after gate activity is exactly the definition of a retry. Using `status` transitions alone is insufficient because `status: verifying → running` happens within an attempt (not between them) in some retry paths.

**Edge cases handled:**
- A journal that contains `*_result` entries but no `current_step` transitions (possible for changes that never retried). The transform treats the whole journal as a single attempt ending at the terminal status.
- A journal interrupted mid-gate (daemon crash). The last gate run has `result: null` and the transform marks it `running`; the attempt's `outcome` is `in-progress`.
- Multiple `current_step: implement` entries in a row (pre-retry reset + retry). The transform coalesces consecutive identical `current_step` values.
- Merge conflict retry (last node in the attempt is `merge` with `result: fail`). The transform sets `retryReason: 'merge-conflict'` instead of `'gate-fail'`.

### Decision 3: Layout — fixed grid, manually positioned, no auto-layout

The layout is a plain `attempt row × gate column` grid. Node `(j, k)` (j = gate position in attempt, k = attempt index) sits at:

```
x = leftMargin + j * (nodeWidth + columnGap)
y = (k - 1) * (rowHeight + attemptGap)
```

Edges are either:
- **Happy (horizontal):** `type: 'default'`, solid neutral-500 1.5px stroke, connects adjacent gate nodes within an attempt.
- **Fail marker (horizontal):** same source/target as happy but dropped; instead the failing node itself renders in red. No outgoing happy edge from a fail node.
- **Retry (smoothstep down):** `type: 'smoothstep'`, 2px stroke, color depends on `retryReason` (amber for gate-fail, orange for merge-conflict, violet for replan). Source handle on the bottom of the failing node, target handle on the top of the next attempt's first node.

**Rationale:** the graph topology is known statically (gates run in a fixed order, attempts stack vertically), so there is no layout problem to solve algorithmically. A fixed-grid layout produces a predictable, readable result and is ~40 lines of code vs. an auto-layout lib that would add another dep.

**Alternatives considered:**
- **Dagre auto-layout.** Rejected — overkill, another dep, and the resulting layout is less predictable than the grid.
- **ELK.js.** Same rejection reasons, bigger footprint.

### Decision 4: Gate rendering — only gates that actually ran appear in the graph

Skipped gates (`result: 'skip'`) are not rendered as nodes. A change that doesn't run e2e (because the project has no e2e setup) does not get an `e2e` column at all. The layout collapses — each attempt's gate columns are whatever gates had at least one `*_result` entry in the journal.

**Rationale:** showing a skipped gate as a faded pill adds visual noise without adding information. Users care about what ran and what that produced, not about what was skipped for unrelated project-level reasons.

**Caveat:** if different attempts skip different gates (attempt 1 skipped `rules`, attempt 2 ran `rules`), the layout keeps gate columns consistent across attempts — meaning attempt 1 gets a single blank spot where `rules` would be. This preserves visual alignment so users can compare attempts side-by-side.

### Decision 5: Polling — reuse existing 10s interval, full re-fetch

The `ChangeDagPanel` fetches `/journal` on mount and every 10 seconds (matching `ChangeTimelineDetail`). Each fetch returns the full journal (typically 1–20 KB), and the transform re-runs to produce a fresh `AttemptGraph`. React Flow diffs the node/edge arrays and updates positions in place.

**Rationale:** the journal endpoint is cheap, the transform is fast (~1 ms for 50 entries), and the 10s cadence is good enough for orchestration monitoring. Building a diff-based incremental update path adds complexity for no user-visible benefit at current scale.

**Future optimization (out of scope):** the journal has a `seq` field, so a `GET /journal?since_seq=N` path is trivially addable if polling cost ever matters. The `AttemptGraph` transform is structured so incremental update would be a drop-in replacement.

### Decision 6: Detail panel — clicking a node opens an inline panel, not a modal

Selecting a node by click opens a `DagDetailPanel` under the graph (not over it). The panel shows:
- Gate name, attempt number, run index, started-at time, duration
- Verdict source (`fast_path`, `classifier_confirmed`, `classifier_override`, `classifier_downgrade`, `classifier_failed`)
- Downgrade audit trail (rendered as a small table: `from → to · reason`) when the source is `classifier_downgrade` or when the sidecar has non-empty `downgrades`
- Full gate output (the `*_output` field, rendered in a `<pre>` with syntax-preserving whitespace)
- Linked issue IDs (when the `issueRefs` array is non-empty), each a link to the issue detail page

**Rationale:** a modal forces a context switch; an inline panel keeps the graph visible so users can click other nodes to compare. The panel can be dismissed by clicking the selected node again or by pressing Escape.

**Default state:** no node selected. The panel shows a hint ("Click a gate node to inspect its run").

### Decision 7: Impl node time — derived from status window, not gate entries

`current_step: implement` is the only signal for the impl phase. The impl node's duration is computed as:

```
impl_duration = (first gate-result entry in attempt).ts - (current_step→implement entry).ts
```

If there is no subsequent gate entry (the impl is still running), the duration is `now - started`. The impl node's `result` field is derived from the subsequent gate activity: `running` if no gates started yet, `pass` if any gate ran afterwards (implying impl completed), never `fail` (impl failure is represented by the attempt outcome, not an impl-node color).

**Rationale:** this is the best signal available in the journal without joining another endpoint. Token and model info would be nicer, but that lives in `getChangeTimeline` and requires a join. Iter 2 can enrich the impl node with tokens; iter 1 ships time only.

### Decision 8: Backwards compatibility — legacy journals fall back gracefully

If `/journal` returns `{"entries": [], "grouped": {}}` (legacy change with no journal yet), the DAG panel renders an empty-state card:

> *"No journal data for this change yet. Switch to Linear view to see session cards."*

…with a button that flips the toolbar's Linear/DAG toggle.

If `/journal` returns 404 (change not found), the panel shows an error card.

If the transform throws or produces an `AttemptGraph` with zero attempts, the panel falls back to an empty-state card with the same linear-view suggestion.

**Rationale:** no user should ever hit a broken panel because of backwards compatibility issues. The linear view is always available.

### Decision 9: Keep the existing `ChangeTimeline` and `ChangeTimelineDetail`

The `ChangeTimeline` row ribbon in `ChangeTable` is NOT touched. The `ChangeTimelineDetail` linear session view is NOT deleted. The DAG is a third view that takes over the expanded-change area by default, with a toolbar toggle to switch back to the linear view.

**Rationale:**
- The row ribbon gives a table-level scan where users can see 20 changes' states in one glance. Replacing it with a DAG would make the table unreadable.
- The linear view carries session-level info (tokens, model, cache hits) that the DAG does not show. For cost and model debugging, the linear view is the right tool.
- Maintenance risk is low: the DAG and linear view read the same underlying data (journal for DAG, `/timeline` for linear), so they cannot diverge in correctness.

### Decision 10: Lazy-load React Flow to keep the main bundle unchanged

The `ChangeDagPanel` is imported via `React.lazy(() => import('./ChangeDagPanel'))` from its mount point. `@xyflow/react` and its CSS are inside that lazy chunk, so users who never expand a change or never open the Changes tab pay zero bundle cost.

**Rationale:** the main bundle is small (~150 KB gzipped) and we want to keep it that way. Lazy-loading the DAG adds a ~200 ms one-time delay on first expansion, which is an acceptable trade.

## Data Contract

### Frontend-internal types

```typescript
// web/src/lib/dag/types.ts

export type GateKind =
  | 'impl' | 'build' | 'test' | 'e2e' | 'review' | 'smoke'
  | 'scope_check' | 'rules' | 'e2e_coverage' | 'merge' | 'terminal';

export type GateResult =
  | 'pass' | 'fail' | 'warn' | 'skip' | 'running' | null;

export interface AttemptNode {
  id: string;              // 'a1-build', 'a2-test', 'a3-merge'
  attempt: number;         // 1-indexed
  kind: GateKind;
  runIndexForKind: number; // 1 for first build in change, 2 for second, ...
  result: GateResult;
  ms: number | null;
  startedAt: string;       // ISO
  endedAt: string | null;  // ISO or null if still running
  output?: string;         // gate stdout (truncated server-side)
  verdictSource?: string;  // 'fast_path' | 'classifier_*'
  downgrades?: Array<{ from: string; to: string; reason: string }>;
  issueRefs?: string[];
}

export interface Attempt {
  n: number;
  startedAt: string;
  endedAt: string | null;
  outcome: 'retry' | 'merged' | 'failed' | 'in-progress';
  retryReason?: 'gate-fail' | 'merge-conflict' | 'replan' | 'unknown';
  nodes: AttemptNode[];
}

export interface AttemptGraph {
  attempts: Attempt[];
  terminal: 'merged' | 'failed' | 'in-progress';
  totalMs: number;
  totalGateRuns: number;
}
```

### Transform function signature

```typescript
// web/src/lib/dag/journalToAttemptGraph.ts

export function journalToAttemptGraph(
  entries: JournalEntry[],           // raw from /journal (already ts-sorted)
  verdictSidecars?: VerdictSidecar[] // optional — for downgrade info
): AttemptGraph;
```

The transform is pure: same input → same output, no I/O, no globals. Unit tests feed hand-crafted `JournalEntry[]` arrays and assert the resulting `AttemptGraph`.

### Layout function signature

```typescript
// web/src/lib/dag/layout.ts

export interface LayoutConstants {
  nodeWidth: number;      // 150
  nodeHeight: number;     // 60
  columnGap: number;      // 30
  rowHeight: number;      // 90
  attemptGap: number;     // 20
  leftMargin: number;     // 20
  topMargin: number;      // 20
}

export function layoutAttemptGraph(
  graph: AttemptGraph,
  constants?: Partial<LayoutConstants>
): { nodes: ReactFlowNode[]; edges: ReactFlowEdge[] };
```

The layout function is also pure and unit-testable. It produces React Flow–compatible node and edge objects.

## Component Architecture

```
<ChangeDagPanel project changeName>                 (entry — fetches journal)
  │ state: journal | error | loading
  │ state: selectedNodeId
  │ state: viewMode ('dag' | 'linear')
  │
  ├─ <DagToolbar>
  │    ├─ attempt count
  │    ├─ total duration
  │    ├─ total gate-run count
  │    └─ <ViewToggle /> (DAG | Linear)
  │
  ├─ (if viewMode === 'linear')
  │    <ChangeTimelineDetail project changeName />   (existing, unchanged)
  │
  └─ (if viewMode === 'dag' && graph.attempts.length > 0)
       <ReactFlow
           nodes={layout.nodes}
           edges={layout.edges}
           nodeTypes={{ gate: GateNode, impl: ImplNode, terminal: TerminalNode }}
           fitView
           minZoom={0.3}
           maxZoom={2}
           nodesDraggable={false}
           nodesConnectable={false}
           onNodeClick={(_, node) => setSelectedNodeId(node.id)}
       >
         <Background variant="dots" gap={20} />
         <MiniMap pannable zoomable />
         <Controls showInteractive={false} />
       </ReactFlow>

       (if selectedNodeId)
         <DagDetailPanel node={selectedNode} onClose={() => setSelectedNodeId(null)} />

  (if empty)
       <EmptyState message="No journal data" suggestLinearView />
```

The `ChangeDagPanel` is the only stateful component. Everything downstream is presentational.

## Risks / Trade-offs

1. **Visual clutter on very high retry counts.** A change that retries 10+ times produces 70+ nodes. React Flow handles this via pan/zoom, but the first-time user may be confused by scrolling. Mitigation: fit-view on load, MiniMap always visible, linear view always available as a toggle.
2. **Layout stability during live updates.** When new nodes arrive during a poll, existing nodes should stay in place and new nodes should flow in at predictable positions. The fixed-grid layout guarantees this — nothing moves because positions are derived from indices.
3. **@xyflow/react version drift.** React Flow 12 renamed from `react-flow-renderer`; pinning a caret version (`^12.x`) is safe. Mitigation: lock to a specific minor in `package.json` and upgrade deliberately.
4. **Transform correctness on pathological journals.** Daemon restart mid-attempt, interrupted gates, out-of-order seqs after crash recovery. Mitigation: extensive unit tests covering each case; fallback to linear view on transform failure.
5. **Duplication between the gate ribbon, DAG, and linear view.** Three views reading overlapping data. Mitigation: all three derive from the same backend endpoints so they cannot diverge; component tests assert consistency between the DAG and the journal data.

## Test Plan

**Unit tests (Vitest):**
- `journalToAttemptGraph.test.ts` — 15+ cases covering:
  - Happy path (one attempt, all gates pass, terminal merged)
  - Single retry (attempt 1 fails test, attempt 2 passes, terminal merged)
  - Merge conflict retry (all gates pass, merge fails, retry, merge succeeds)
  - Classifier downgrade (review gate with `warn` and non-empty `downgrades`)
  - Interrupted run (no terminal status, last gate result is null)
  - Legacy empty journal (empty entries array → AttemptGraph with zero attempts)
  - Pathological out-of-order seqs (daemon restart case)
  - Skipped gate (e2e not run; the column collapses in layout)
  - Mixed attempts with different gate subsets (attempt 1 runs scope_check, attempt 2 doesn't)
- `layout.test.ts` — 5 cases covering node/edge position math for 1, 2, 3, 5, 10 attempts.

**E2E tests (Playwright):**
- `change-state-dag.spec.ts` — three cases:
  1. DAG renders with correct attempt count for a seeded multi-attempt change
  2. Click on a gate node opens the detail panel with the correct output text
  3. Linear view toggle switches the rendered component
- Seed via `E2E_PROJECT` env var pointing at a fixture project; no mocks.

**Manual testing:**
- Open the Changes tab for a real multi-retry change from a completed run; verify the DAG visually matches the journal JSONL content read directly with `cat`.
- Resize the browser window; verify fit-view keeps the graph readable.
- Toggle between DAG and Linear views; verify no state loss.

## Migration

No migration needed. The change is purely additive to the web frontend. Legacy changes without journals fall back to the linear view automatically.

## Open Questions

- **Impl-node token info.** Currently the DAG impl node shows duration only. Joining with `/timeline` would add token counts and model info. Decision: **not** in this iteration — ship the DAG with duration-only impl nodes, add enrichment as a follow-up if users ask for it.
- **Issue integration.** The detail panel shows linked issue IDs if present, but the data contract (`issueRefs` on `AttemptNode`) is not yet populated by the journal endpoint. Decision: **specify the field** in the types but leave it empty in iteration 1. The issue-linking work belongs in a separate change.
- **Canonical view toggle.** Could be added as a third view mode later. Decision: **out of scope** for this change.
