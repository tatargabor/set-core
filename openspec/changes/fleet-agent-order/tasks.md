## 1. The store (core)

- [x] 1.1 Add `save_agent_order(order, *, project)` to `lib/set_orch/fleet/layout.py`, following `save_docks` — per project, last-write-wins, stored verbatim [REQ: storing-the-order-does-not-fight-the-arrangement]
- [x] 1.2 Serve the stored orders from `GET /api/fleet/layout` as `agent_order` [REQ: storing-the-order-does-not-fight-the-arrangement]
- [x] 1.3 Add `PUT /api/fleet/layout/agent-order`, refusing a body with no project, the way `fleet_put_docks` does [REQ: storing-the-order-does-not-fight-the-arrangement]
- [x] 1.4 Python tests: the order round-trips, it is per project, it does not touch `version`, and a body with no project is refused [REQ: storing-the-order-does-not-fight-the-arrangement]

## 2. What the order means (web lib)

- [x] 2.1 Add `web/src/lib/fleetAgentOrder.ts` with `agentKey(agent)` — terminal label, then name, then `pid:<n>` [REQ: the-order-is-stored-by-a-durable-identity]
- [x] 2.2 `orderAgents(agents, order)`: named agents in the stored order, then the rest in discovery's order [REQ: what-the-order-does-not-name-and-what-is-not-running]
- [x] 2.3 `moveKey(order, agents, from, to)`: the stored list after a move, keeping entries discovery did not return [REQ: what-the-order-does-not-name-and-what-is-not-running]
- [x] 2.4 Vitest for all three, including a restart (same keys, new pids), a rename, an unknown agent, and a stored key that is not running [REQ: the-order-is-stored-by-a-durable-identity]

## 3. The gesture, shared with the project column

- [x] 3.1 Extract `useReorder` from `FleetProjectColumn.tsx` into `web/src/lib/useReorder.ts`, taking an axis [REQ: the-reader-can-order-a-projects-agents-by-hand]
- [x] 3.2 The column keeps its behaviour — its existing tests must pass UNEDITED [REQ: the-reader-can-order-a-projects-agents-by-hand]
- [x] 3.3 `x` axis: the midpoint test reads `clientX` and `width` [REQ: the-reader-can-order-a-projects-agents-by-hand]

## 4. The strip and the grid

- [x] 4.1 `AgentTabs` becomes reorderable: each tab is a drag item, with the keyboard path on the tab itself [REQ: the-reader-can-order-a-projects-agents-by-hand]
- [x] 4.2 A press-and-release still only SELECTS — the engagement threshold is what separates them [REQ: the-reader-can-order-a-projects-agents-by-hand]
- [x] 4.3 Sort `gridAgents` by the order, after the dock filter, and hand that same array to the strip [REQ: one-order-governs-the-tabs-and-the-grid]
- [x] 4.4 Save on drop and on each keyboard move, optimistically — the screen shows the new order before the write returns [REQ: storing-the-order-does-not-fight-the-arrangement]
- [x] 4.5 Carry the order through a rename, beside the docks [REQ: the-order-is-stored-by-a-durable-identity]

## 5. Tests

- [x] 5.1 Vitest on the strip: a keyboard move reorders and posts; a click does not post; the posted body carries the project and the keys [REQ: the-reader-can-order-a-projects-agents-by-hand]
- [x] 5.2 Vitest that the grid renders in the stored order [REQ: one-order-governs-the-tabs-and-the-grid]
- [x] 5.3 Mutation-prove each rule: unknown-agents-first, stored-list-pruned, order-ignored-by-the-grid, pid-as-identity, threshold-removed [REQ: what-the-order-does-not-name-and-what-is-not-running]
- [x] 5.4 Full web suite and the Python suite green, with the project column's tests unedited [REQ: the-reader-can-order-a-projects-agents-by-hand]

## 6. Deploy and look at it

- [x] 6.1 `pnpm build` and restart `set-web` [REQ: one-order-governs-the-tabs-and-the-grid]
- [x] 6.2 Drag a tab on the running screen, reload the page, and report what came back [REQ: one-order-governs-the-tabs-and-the-grid]
  - **DONE, and here is exactly what was seen** (2026-08-26, Chrome on the running dashboard, a project with two agents): the strip read `<a> | <b>`; dragging the second tab to the left made it read `<b> | <a>`, and the SELECTED tab did not change — the drag moved the agent without also enlarging it. `GET /api/fleet/layout` then answered `agent_order: {<project>: ['<b>', '<a>']}`. After a full page reload the strip still read `<b> | <a>`, and returning to the grid put the tiles in that same order.
  - The probe order was removed afterwards (`PUT … {"order": []}` → the key is gone), so the reader's screen is exactly as it was before the check.

## Acceptance Criteria (from spec scenarios)

- [x] AC-1: WHEN a person drags a tab past another and releases THEN the agent moves there and the order is stored [REQ: the-reader-can-order-a-projects-agents-by-hand, scenario: a-tab-is-dragged-to-a-new-position]
- [x] AC-2: WHEN a person moves a focused tab with the keyboard THEN the agent moves one position and the order is stored [REQ: the-reader-can-order-a-projects-agents-by-hand, scenario: a-tab-is-moved-with-the-keyboard]
- [x] AC-3: WHEN a person presses a tab and releases without moving THEN the order is unchanged and the tab is selected [REQ: the-reader-can-order-a-projects-agents-by-hand, scenario: a-click-is-not-a-drag]
- [x] AC-4: WHEN the reader reorders the tabs and returns to the grid THEN the tiles are in the same order [REQ: one-order-governs-the-tabs-and-the-grid, scenario: the-grid-follows-the-strip]
- [x] AC-5: WHEN a project is opened with a stored order THEN both tabs and tiles start in that order [REQ: one-order-governs-the-tabs-and-the-grid, scenario: the-strip-follows-the-grids-order-on-arrival]
- [x] AC-6: WHEN the agents restart with new pids THEN each returns to the position the reader gave it [REQ: the-order-is-stored-by-a-durable-identity, scenario: the-agents-restart]
- [x] AC-7: WHEN an agent is renamed THEN it keeps its position [REQ: the-order-is-stored-by-a-durable-identity, scenario: an-agent-is-renamed]
- [x] AC-8: WHEN an agent the order does not name appears THEN it is shown last and nothing placed moves [REQ: what-the-order-does-not-name-and-what-is-not-running, scenario: a-newly-started-agent]
- [x] AC-9: WHEN an ordered agent stops and later runs again THEN it returns to its position [REQ: what-the-order-does-not-name-and-what-is-not-running, scenario: an-agent-stops-and-comes-back]
- [x] AC-10: WHEN an agent order is stored THEN the arrangement's version is neither required nor advanced [REQ: storing-the-order-does-not-fight-the-arrangement, scenario: ordering-while-the-arrangement-is-being-edited]
- [x] AC-11: WHEN two projects both have a stored order THEN each applies only to its own agents [REQ: storing-the-order-does-not-fight-the-arrangement, scenario: the-order-is-per-project]
