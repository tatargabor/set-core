## Why

The fleet screen lists projects as flat rows; the agents working inside a project are visible
only after selecting the project and reading the content area. Selecting a specific agent costs
a second click on the right-hand pane, and nothing on the left answers "where is that agent in
its work?" — which change it is on and which lifecycle phase that change is in. Agents are
started to carry work through a flow (plan, implement, verify, ship); the flow's position is the
single most useful fact about the agent, and the screen does not show it.

The rendering mechanic this needs already exists: the declared stage-order strip shipped for the
project-status table draws a declared order of stages, counts what sits in each, draws empty
stages, and marks values outside the order. What is missing is a per-agent stage value to feed
it, and a tree home for it on the fleet screen.

## What Changes

- The fleet project column gains a **tree**: each project row can expand to indented sub-rows,
  one per live agent under that project. Sub-rows are visually subordinate (indented, smaller).
- Clicking an agent sub-row **selects that agent** — same effect as selecting its tile in the
  content area today (project selected, agent enlarged/focused).
- Each agent sub-row renders a **compact stage strip**: the agent's flow as an ordered set of
  stages, with completed stages, the current stage, and pending stages visually distinguished;
  an agent with no active work renders the empty state, and a stage value the flow does not
  declare is marked as outside the flow, never dropped or silently bucketed.
- The fleet agent payload (`GET /api/fleet/agents`) gains a per-agent **stage** field, resolved
  by the framework:
  - **Default (derived, zero producer work):** the OpenSpec lifecycle of the project the agent
    runs in — proposal → design → apply → verify → archive — derived from the project's
    `openspec/changes/` tree, joined to the agent's session. Any project using OpenSpec gets
    agent stages without declaring anything.
  - **Declared override:** a producer may declare its own flow through the existing
    project-status contract (`stageOrder` on a stage field); the declared flow replaces the
    derived one for that project's agents. The framework stays domain-free — it renders stages,
    it does not know what they mean.
- A gap (agent on no change, change unresolvable, project has no flow) is **reported as a gap,
  never filled** — the same refusal this codebase already applies to work-cycle purposes.
- Nothing derived from a consumer's data is persisted: the stage is computed per request from
  the project's tree and the producer's declared answer.

## Capabilities

### New Capabilities
- `agent-stage-derivation`: resolving a per-agent stage (flow + current position + progress)
  from the project's OpenSpec tree or the producer's declared stage order, and exposing it on
  the fleet agent payload. Owns the derivation rules, the join to sessions, the gap semantics,
  and the declared-override precedence.
- `fleet-agent-tree`: the fleet project column's agent sub-rows — tree layout, agent selection
  from the row, and the compact per-agent stage strip rendering (done / current / pending /
  empty / outside-the-flow).

### Modified Capabilities
<!-- none: stageOrder's contract and rendering are unchanged; this change is a new READER of
     the declared order and a new renderer instance of the same mechanic. The fleet payload's
     existing fields are untouched; `stage` is additive and owned by agent-stage-derivation. -->

## Impact

- `lib/set_orch/api/fleet.py` — `_agent_payload` gains the resolved stage; a new resolver module
  beside `fleet/purpose.py` does the derivation (Python lift of the phase machine in
  `lib/loop/prompt.sh` `detect_next_change_action`, extended to the full axis, reusing
  `read_progress` for task counts).
- `web/src/components/FleetProjectColumn.tsx`, `web/src/lib/fleetColumnView.ts`,
  `web/src/lib/fleetTypes.ts` — tree rows, sub-row rendering, `stage` type; agent click wires to
  the existing `writeView(project, {enlarged: pid})` selection mechanism.
- Reuses, unchanged: `web/src/lib/stageGroups.ts` grouping semantics and the project-status
  contract's `stageOrder` validation (`lib/set_orch/project_status.py`).
- No contract change for producers: the default path requires nothing from the project side.
