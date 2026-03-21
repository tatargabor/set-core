# Tasks: timeline-iteration-blocks

## 1. Backend — Enrich timeline API with iteration data

- [x] 1.1 In `_build_change_timeline()` (api.py ~L2360), after reading gate results from `orchestration-state.json`, also read `worktree_path` for the change from the same state data [REQ: timeline-api-returns-iteration-enriched-data]
- [x] 1.2 Read `<worktree_path>/.set/loop-state.json` and extract the `iterations` array; if file not found, use empty list [REQ: timeline-api-returns-iteration-enriched-data]
- [x] 1.3 Implement state assignment: for each iteration, find the most recent STATE_CHANGE transition where `ts <= iteration.started` and assign that transition's `to` as the iteration's `state` (default to `"running"`) [REQ: timeline-api-returns-iteration-enriched-data]
- [x] 1.4 Build the `iterations` response array with fields: `n`, `started`, `ended`, `state`, `commits` (count), `tokens_used`, `timed_out`, `no_op` [REQ: timeline-api-returns-iteration-enriched-data]
- [x] 1.5 Add `iterations` key to the returned dict (empty list for non-Ralph changes) [REQ: timeline-api-returns-iteration-enriched-data]

## 2. Frontend — Update TypeScript types

- [x] 2.1 Update `ChangeTimelineData` interface in `api.ts` to add `iterations` array with typed fields: `n: number, started: string, ended: string, state: string, commits: number, tokens_used: number, timed_out: boolean, no_op: boolean` [REQ: frontend-renders-iteration-based-timeline]

## 3. Frontend — Rewrite ChangeTimelineDetail component

- [x] 3.1 Add iteration block rendering: map over `data.iterations` to render small colored blocks (`w-6 h-6 rounded`) using STATE_COLORS[iteration.state], arranged in a flex-wrap horizontal flow [REQ: frontend-renders-iteration-based-timeline]
- [x] 3.2 Add state boundary markers: when consecutive iterations have different `state` values, render a vertical separator line and state label between them [REQ: frontend-renders-iteration-based-timeline]
- [x] 3.3 Add hover tooltip on each iteration block showing: iteration number, duration, tokens, commits, state, and flags (timed_out, no_op) [REQ: frontend-renders-iteration-based-timeline]
- [x] 3.4 Add fallback: when `data.iterations.length === 0`, render the existing state-transition block view (current behavior preserved) [REQ: frontend-renders-iteration-based-timeline]

## 4. Build and verify

- [x] 4.1 Run `pnpm build` in web/ to verify TypeScript compiles without errors [REQ: frontend-renders-iteration-based-timeline]

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN change has loop-state.json with iterations THEN API returns iterations array with state assigned per iteration [REQ: timeline-api-returns-iteration-enriched-data, scenario: change-with-loop-state-iterations]
- [x] AC-2: WHEN change has no loop-state.json THEN API returns empty iterations array [REQ: timeline-api-returns-iteration-enriched-data, scenario: change-without-loop-state]
- [x] AC-3: WHEN timeline has iterations THEN each renders as colored block with state-based color [REQ: frontend-renders-iteration-based-timeline, scenario: iteration-blocks-rendering]
- [x] AC-4: WHEN consecutive iterations have different states THEN separator and label shown [REQ: frontend-renders-iteration-based-timeline, scenario: state-boundary-markers]
- [x] AC-5: WHEN user hovers iteration block THEN tooltip shows details [REQ: frontend-renders-iteration-based-timeline, scenario: iteration-hover-details]
- [x] AC-6: WHEN no iterations data THEN fallback to state-transition view [REQ: frontend-renders-iteration-based-timeline, scenario: fallback-for-non-iteration-changes]
