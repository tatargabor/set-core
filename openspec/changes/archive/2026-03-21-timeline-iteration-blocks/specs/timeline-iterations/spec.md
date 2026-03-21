# Delta Spec: timeline-iterations

## ADDED Requirements

## IN SCOPE
- Timeline API returns per-iteration blocks with state context
- Frontend renders iterations as individual visual blocks in horizontal flow
- State boundaries shown as color changes and separator markers between iteration blocks
- Iterations without loop-state data (non-Ralph changes) fall back to state-transition-only view
- Tooltip/hover showing iteration details (tokens, commits, duration)

## OUT OF SCOPE
- Clickable iteration blocks linking to per-iteration logs (future feature)
- Real-time live-updating timeline via WebSocket/SSE
- Timeline for multi-agent (team mode) sub-iterations
- Changes to loop-state.json schema

### Requirement: Timeline API returns iteration-enriched data
The timeline API SHALL return a unified list of iteration blocks enriched with state context, merging STATE_CHANGE events with loop-state.json iteration history.

#### Scenario: Change with loop-state iterations
- **WHEN** GET `/api/{project}/changes/{name}/timeline` is called
- **AND** the change has a `loop-state.json` with an `iterations` array
- **THEN** the response SHALL include an `iterations` array where each entry contains:
  - `n`: iteration number
  - `started`: ISO timestamp
  - `ended`: ISO timestamp
  - `state`: the orchestration state active during this iteration (e.g., "running", "dispatched")
  - `commits`: number of commits made
  - `tokens_used`: tokens consumed
  - `timed_out`: boolean
  - `no_op`: boolean (no meaningful work)
- **AND** the `transitions` array SHALL still be included for state boundary markers

#### Scenario: Change without loop-state (non-Ralph)
- **WHEN** GET `/api/{project}/changes/{name}/timeline` is called
- **AND** no `loop-state.json` exists for the change
- **THEN** the response SHALL return only `transitions` (current behavior)
- **AND** the `iterations` array SHALL be empty

#### Scenario: State assignment to iterations
- **WHEN** building the iteration list
- **THEN** each iteration SHALL be assigned the orchestration state that was active at that iteration's `started` timestamp
- **AND** state assignment SHALL be derived by finding the most recent STATE_CHANGE event with `ts <= iteration.started`

### Requirement: Frontend renders iteration-based timeline
The ChangeTimelineDetail component SHALL render each iteration as an individual block in a horizontal flow, with state indicated by color.

#### Scenario: Iteration blocks rendering
- **WHEN** the timeline has iterations data
- **THEN** each iteration SHALL be rendered as a small colored block (circle or rounded square)
- **AND** the block color SHALL correspond to the iteration's `state` using the existing STATE_COLORS palette
- **AND** blocks SHALL be arranged left-to-right in chronological order

#### Scenario: State boundary markers
- **WHEN** consecutive iterations have different `state` values
- **THEN** a visual separator SHALL be rendered between them
- **AND** the new state name SHALL be displayed as a label above or below the separator

#### Scenario: Iteration hover details
- **WHEN** user hovers over an iteration block
- **THEN** a tooltip SHALL display:
  - Iteration number (e.g., "Iteration 5/30")
  - Duration (from `started` to `ended`)
  - Tokens used
  - Commits count
  - State name
  - Flags: timed_out, no_op (if true)

#### Scenario: Fallback for non-iteration changes
- **WHEN** the timeline has no iterations data (empty array)
- **THEN** the component SHALL fall back to the current state-transition block rendering
- **AND** existing behavior SHALL be preserved exactly

#### Scenario: State-only transitions without iterations
- **WHEN** the timeline has transitions but the change never entered "running" state (e.g., pending → failed)
- **THEN** only state blocks SHALL be shown (no iteration blocks)
- **AND** state blocks SHALL use the existing large-block rendering style
