# change-state-dag Specification

## Purpose
TBD - created by archiving change add-change-state-dag. Update Purpose after archive.
## Requirements
### Requirement: DAG panel entry point
The web dashboard SHALL provide a `ChangeDagPanel` React component that is mounted in the expanded-change area of the Changes tab.

#### Scenario: Panel mounts with a valid change
- **WHEN** a user expands a change row in the Changes tab
- **THEN** `ChangeDagPanel` is rendered inside the expanded area
- **THEN** the panel fetches `GET /api/{project}/changes/{name}/journal` on mount
- **THEN** while the fetch is in flight a loading state is shown

#### Scenario: Panel re-fetches on poll interval
- **WHEN** the panel has been mounted for 10 seconds
- **THEN** a new fetch to the journal endpoint is issued
- **THEN** the React Flow graph is re-rendered with the updated `AttemptGraph`
- **THEN** nodes that already existed keep their positions (fixed-grid layout is stable under re-render)

#### Scenario: Panel unmounts and clears its interval
- **WHEN** the user collapses the change row or navigates away
- **THEN** the polling interval is cleared
- **THEN** no further network requests are made for this change

### Requirement: Lazy-loaded React Flow bundle
The DAG panel SHALL be loaded via `React.lazy` so that `@xyflow/react` is not included in the main bundle.

#### Scenario: User who never opens the Changes tab
- **WHEN** a user loads the dashboard and never opens the Changes tab
- **THEN** the `@xyflow/react` chunk is not downloaded
- **THEN** the main bundle size is unaffected by this change

#### Scenario: First expansion loads the lazy chunk
- **WHEN** a user opens the Changes tab and expands a change for the first time
- **THEN** the lazy chunk containing `ChangeDagPanel` and `@xyflow/react` is downloaded
- **THEN** a Suspense fallback is shown during the chunk load
- **THEN** subsequent expansions use the already-loaded chunk without re-downloading

### Requirement: Journal-to-graph transform
The web code SHALL provide a pure function `journalToAttemptGraph(entries, verdictSidecars?)` that converts raw journal entries into an `AttemptGraph` structure.

#### Scenario: Transform is pure
- **WHEN** the same input array is passed twice to the transform
- **THEN** the returned `AttemptGraph` is deeply equal in both calls
- **THEN** the transform performs no I/O and reads no globals

#### Scenario: Single-attempt happy path
- **WHEN** the transform receives a journal with one `current_step: implement` entry followed by `build_result: pass`, `test_result: pass`, `e2e_result: pass`, `status: merged`
- **THEN** the returned graph has exactly one attempt
- **THEN** that attempt has `outcome: 'merged'` and nodes for impl, build, test, e2e, and a terminal node
- **THEN** the graph's `terminal` field is `'merged'`

#### Scenario: Multi-attempt with retries
- **WHEN** the transform receives a journal with three `current_step: implement` transitions and gate-result entries between them
- **THEN** the returned graph has exactly three attempts
- **THEN** attempt 1's `outcome` is `'retry'` with `retryReason` matching the failed gate type
- **THEN** attempts 2 and 3 are chronologically ordered
- **THEN** `runIndexForKind` increments across attempts (e.g. the build node in attempt 2 has `runIndexForKind: 2`)

#### Scenario: Merge-conflict retry reason
- **WHEN** the transform sees an attempt where all gates pass but the final `merge_result` is `fail` (or the `status` transitions to `running` after a merge attempt)
- **THEN** that attempt's `retryReason` is `'merge-conflict'`
- **THEN** a downstream consumer (the layout) renders the retry edge in a merge-conflict color

#### Scenario: Interrupted attempt
- **WHEN** the transform sees a journal with gate-result entries but no terminal `status: merged` or `status: failed`
- **THEN** the last attempt's `outcome` is `'in-progress'`
- **THEN** the graph's `terminal` field is `'in-progress'`
- **THEN** if the last gate result is null the corresponding node has `result: 'running'`

#### Scenario: Empty journal
- **WHEN** the transform receives an empty entries array
- **THEN** the returned graph has zero attempts
- **THEN** the graph's `terminal` field is `'in-progress'`
- **THEN** `totalGateRuns` is 0

#### Scenario: Skipped gate
- **WHEN** the transform sees a `*_result` entry with value `'skip'`
- **THEN** a node for that gate is NOT added to the attempt
- **THEN** the layout does not allocate a column for that gate in that attempt

#### Scenario: Out-of-order seq after daemon restart
- **WHEN** the transform receives entries that are `ts`-sorted but have duplicate or non-monotonic `seq` values due to daemon restart
- **THEN** the transform processes them in `ts` order (the primary key)
- **THEN** `seq` is used only as a tiebreaker for entries with equal `ts`

### Requirement: Fixed-grid layout function
The web code SHALL provide a pure function `layoutAttemptGraph(graph)` that produces React Flow–compatible node and edge arrays.

#### Scenario: Layout is deterministic
- **WHEN** the same `AttemptGraph` is laid out twice
- **THEN** node positions are identical byte-for-byte

#### Scenario: Attempt rows are vertically stacked
- **WHEN** the layout receives a graph with 3 attempts
- **THEN** attempt 1 nodes have `y = 20` (top margin)
- **THEN** attempt 2 nodes have `y = 20 + rowHeight + attemptGap`
- **THEN** attempt 3 nodes have `y = 20 + 2 * (rowHeight + attemptGap)`

#### Scenario: Gate columns are horizontally spaced
- **WHEN** the layout receives an attempt with 5 gate nodes
- **THEN** the 5 nodes are horizontally spaced at `x = leftMargin + j * (nodeWidth + columnGap)` for `j = 0..4`

#### Scenario: Happy edges connect adjacent gates
- **WHEN** an attempt has gate nodes in sequence
- **THEN** each pair of adjacent gate nodes has a `type: 'default'` edge between them
- **THEN** the edge color is a neutral gray

#### Scenario: Retry edges loop back to next attempt
- **WHEN** attempt 1 ends with a failing gate and attempt 2 begins
- **THEN** a `type: 'smoothstep'` edge connects the failing node to attempt 2's first node
- **THEN** the source handle is on the bottom of the failing node
- **THEN** the target handle is on the top of attempt 2's first node

#### Scenario: Merge-conflict retry edge color differs from gate-fail
- **WHEN** an attempt's `retryReason` is `'merge-conflict'`
- **THEN** the retry edge uses an orange stroke color
- **WHEN** an attempt's `retryReason` is `'gate-fail'`
- **THEN** the retry edge uses an amber stroke color

### Requirement: Gate node rendering
The DAG SHALL render a custom `GateNode` React Flow node type for every gate run.

#### Scenario: Compact gate node shows icon + name + duration
- **WHEN** a gate node is rendered in its default (non-hovered, non-selected) state
- **THEN** the node is 150px wide by 60px tall
- **THEN** the node shows a result icon (`✓`, `✗`, `⚠`, `–`, or `●` pulse)
- **THEN** the node shows the gate name
- **THEN** the node shows the duration in human-readable format (e.g. `3.4s`, `1m48s`)

#### Scenario: Run-index badge appears for cross-attempt re-runs
- **WHEN** a gate node represents the 2nd or later run of that gate type within the change
- **THEN** a `⟳N` badge is shown in the node header where `N` is the `runIndexForKind`
- **WHEN** a gate node is the 1st run of its type
- **THEN** no `⟳N` badge is shown

#### Scenario: Classifier downgrade indicator
- **WHEN** a gate node has a non-empty `downgrades` array OR its `verdictSource` is `'classifier_downgrade'`
- **THEN** a `⚖` icon is shown next to the run-index badge
- **THEN** clicking the node opens the detail panel with the downgrade audit trail visible

#### Scenario: Current / running node is animated
- **WHEN** a gate node has `result: 'running'`
- **THEN** the node's border is rendered with a pulse animation
- **THEN** the icon shows a blue filled circle (`●`)

#### Scenario: Expanded node on hover
- **WHEN** the user hovers a gate node
- **THEN** the node resizes to ~260×140px
- **THEN** additional fields become visible: attempt number, started-at time, verdict source
- **WHEN** the hover ends
- **THEN** the node returns to its compact size

### Requirement: Impl node rendering
The DAG SHALL render a custom `ImplNode` React Flow node type for each attempt's implement phase.

#### Scenario: Impl node shows duration
- **WHEN** an impl node is rendered
- **THEN** it displays the impl-phase duration in human-readable format
- **THEN** it displays the attempt number (`impl #1`, `impl #2`, …)
- **THEN** the visual color is distinct from gate nodes (blue/violet accent)

#### Scenario: Impl node is the first node in every attempt row
- **WHEN** an attempt has gates
- **THEN** the impl node is the leftmost node in that attempt's row
- **THEN** a horizontal happy edge connects the impl node to the first gate node of the attempt

### Requirement: Terminal node rendering
The DAG SHALL render a `TerminalNode` at the end of the trajectory when the change has reached a terminal state.

#### Scenario: Merged terminal
- **WHEN** the graph's `terminal` field is `'merged'`
- **THEN** a large green terminal node labeled `MERGED ✓` is rendered at the end of the last attempt's row
- **THEN** the node shows the attempt number where the merge succeeded and the total duration

#### Scenario: Failed terminal
- **WHEN** the graph's `terminal` field is `'failed'`
- **THEN** a large red terminal node labeled `FAILED ✗` is rendered
- **THEN** the node shows a short failure reason when one is available (e.g. `max retries exceeded`)

#### Scenario: In-progress has no terminal
- **WHEN** the graph's `terminal` field is `'in-progress'`
- **THEN** no terminal node is rendered
- **THEN** the most recent running or completed gate node is the last node in the graph

### Requirement: Detail panel on node click
The DAG SHALL provide a `DagDetailPanel` that opens under the graph when a node is clicked.

#### Scenario: Click opens the detail panel
- **WHEN** the user clicks a gate or impl node
- **THEN** the detail panel opens under the React Flow canvas
- **THEN** the panel shows gate name, attempt number, run index, started-at time, and duration
- **THEN** the panel shows the full gate output in a preformatted block

#### Scenario: Downgrade audit trail visible
- **WHEN** the selected node has a non-empty `downgrades` array
- **THEN** a "Classifier downgrades" section is visible in the panel
- **THEN** the section shows each downgrade as `from → to · reason`

#### Scenario: Click outside deselects
- **WHEN** a node is selected and the user clicks the React Flow background or presses Escape
- **THEN** the detail panel closes
- **THEN** the selected node returns to its default visual state

#### Scenario: Re-clicking selected node toggles panel closed
- **WHEN** the user clicks a node that is already selected
- **THEN** the detail panel closes
- **THEN** `selectedNodeId` is cleared

### Requirement: Toolbar with DAG/Linear view toggle
The panel SHALL provide a toolbar above the graph with summary counts and a view-mode toggle.

#### Scenario: Toolbar shows summary counts
- **WHEN** the panel has a loaded `AttemptGraph`
- **THEN** the toolbar displays the attempt count (e.g. `3 attempts`)
- **THEN** the toolbar displays the total duration (e.g. `8m 14s`)
- **THEN** the toolbar displays the total gate-run count (e.g. `19 gate runs`)

#### Scenario: Toggle switches to linear view
- **WHEN** the user clicks the Linear toggle button
- **THEN** the React Flow canvas is unmounted
- **THEN** `ChangeTimelineDetail` is mounted in its place with the same project/change props
- **THEN** the toolbar remains visible with the DAG option selectable

#### Scenario: Toggle switches back to DAG view
- **WHEN** the user is in Linear view and clicks the DAG toggle button
- **THEN** `ChangeTimelineDetail` is unmounted
- **THEN** the React Flow canvas is mounted with the current `AttemptGraph`

### Requirement: Empty-state handling
The DAG SHALL render a clear empty state when no journal data is available.

#### Scenario: Empty journal on a legacy change
- **WHEN** the panel loads a change whose journal endpoint returns `{"entries": [], "grouped": {}}`
- **THEN** the panel shows an empty-state card with the text "No journal data for this change yet"
- **THEN** the empty state includes a button to switch to Linear view

#### Scenario: Transform failure falls back to linear view
- **WHEN** the `journalToAttemptGraph` transform throws or returns a graph with zero attempts
- **THEN** the panel shows the empty-state card
- **THEN** the panel logs the transform error to the browser console

#### Scenario: Endpoint returns 404
- **WHEN** the journal endpoint returns HTTP 404
- **THEN** the panel shows an error card with the change name
- **THEN** the linear view remains accessible via the toolbar toggle

### Requirement: Existing views coexist unchanged
The change SHALL NOT modify the existing `ChangeTimeline` row ribbon or `ChangeTimelineDetail` linear session view.

#### Scenario: Row ribbon is unchanged
- **WHEN** a user looks at the Changes tab table
- **THEN** each row still shows the existing horizontal gate ribbon rendered by `ChangeTimeline`
- **THEN** no visual regression is introduced in the row view

#### Scenario: Linear view is preserved and reachable
- **WHEN** a user expands a change and toggles to Linear view
- **THEN** the exact existing `ChangeTimelineDetail` component is rendered
- **THEN** its session-card output is identical to the current behavior

### Requirement: E2E test coverage
The change SHALL include Playwright E2E tests that validate the DAG against a real project fixture.

#### Scenario: DAG renders with correct attempt count
- **WHEN** the test visits a change that has N attempts in its journal
- **THEN** the test asserts that N attempt-row groups are visible in the rendered React Flow canvas
- **THEN** the test asserts that the toolbar shows the correct attempt count

#### Scenario: Click on a gate node opens the detail panel
- **WHEN** the test clicks a gate node
- **THEN** the test asserts the detail panel becomes visible
- **THEN** the test asserts the panel shows the expected gate output text

#### Scenario: Linear toggle swaps components
- **WHEN** the test clicks the Linear toggle button in the toolbar
- **THEN** the test asserts the React Flow canvas is no longer visible
- **THEN** the test asserts `ChangeTimelineDetail` session cards are visible in the same area

