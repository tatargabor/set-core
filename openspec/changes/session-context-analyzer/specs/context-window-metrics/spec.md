## MODIFIED Requirements

### Requirement: Context tokens captured at first iteration completion
The monitor SHALL read `context_tokens_start` from `loop-state.json` after the first iteration completes, computed as `cache_create_tokens` from iteration 1. Additionally, if the iteration contains a `context_breakdown` object, the monitor SHALL store the full breakdown in the change's orchestration state.

#### Scenario: Start tokens recorded after iteration 1
- **WHEN** a change's Ralph loop completes its first iteration
- **AND** `loop-state.json` contains `iterations[0].cache_create_tokens`
- **THEN** the change's orchestration state entry has `context_tokens_start = cache_create_tokens` from iteration 1

#### Scenario: Context breakdown recorded when available
- **WHEN** a change's Ralph loop completes its first iteration
- **AND** `iterations[0].context_breakdown` exists in `loop-state.json`
- **THEN** the change's orchestration state SHALL also store `context_breakdown_start` with the full breakdown object

#### Scenario: Start tokens absent if loop-state unavailable
- **WHEN** `loop-state.json` does not exist or has no completed iterations
- **THEN** `context_tokens_start` is not written to state (field absent, not 0)

### Requirement: set-web change list shows context metrics
The set-web change list SHALL display a `ctx` indicator for each change that has `context_tokens_end` in state, showing end tokens and utilization percentage. When `context_breakdown_start` is available, an expandable detail SHALL show the component breakdown.

#### Scenario: Context metric displayed for completed change
- **WHEN** a change has `context_tokens_end = 150_000` in state
- **THEN** the set-web change list shows something like `ctx: 150K (75%)`

#### Scenario: Context metric shows start→end when both available
- **WHEN** a change has both `context_tokens_start = 40_000` and `context_tokens_end = 150_000`
- **THEN** the set-web change list shows `ctx: 40K → 150K (75%)`

#### Scenario: Breakdown tooltip on hover
- **WHEN** a change has `context_breakdown_start` in state
- **AND** the user hovers over the context metric
- **THEN** a tooltip SHALL show the component breakdown: base, memory, prompt, tools

#### Scenario: Context metric absent for changes without data
- **WHEN** a change has no `context_tokens_end` in state (e.g., old state file)
- **THEN** no `ctx` indicator is shown for that change
- **AND** no error or blank column appears

#### Scenario: High context utilization is visually highlighted
- **WHEN** `context_tokens_end / CONTEXT_WINDOW_SIZE >= 0.80`
- **THEN** the context metric is displayed with a warning color or indicator (e.g., orange/red)
