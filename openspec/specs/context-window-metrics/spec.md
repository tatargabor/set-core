## ADDED Requirements

## IN SCOPE
- Capturing context token usage (start and end) per change session from `loop-state.json`
- Storing `context_tokens_start` and `context_tokens_end` in orchestration state per change
- Displaying context metrics in the set-web change list
- Hardcoded 200K context window size constant for Claude 4.x Sonnet/Opus

## OUT OF SCOPE
- Dynamic context window size detection per model
- Per-iteration context sampling (start and end only)
- Context metrics in TUI (set-web only for now)
- Historical context trend charts

### Requirement: Context tokens captured at first iteration completion
The monitor SHALL read `context_tokens_start` from `loop-state.json` after the first iteration completes, computed as `cache_create_tokens` from iteration 1.

#### Scenario: Start tokens recorded after iteration 1
- **WHEN** a change's Ralph loop completes its first iteration
- **AND** `loop-state.json` contains `iterations[0].cache_create_tokens`
- **THEN** the change's orchestration state entry has `context_tokens_start = cache_create_tokens` from iteration 1

#### Scenario: Start tokens absent if loop-state unavailable
- **WHEN** `loop-state.json` does not exist or has no completed iterations
- **THEN** `context_tokens_start` is not written to state (field absent, not 0)

### Requirement: Context tokens captured at loop completion
The monitor SHALL record `context_tokens_end` when a change transitions out of `running` status (to `verifying`, `failed`, or `done`), computed as `total_input_tokens + total_cache_create` from the final `loop-state.json`.

#### Scenario: End tokens recorded at loop completion
- **WHEN** a change's Ralph loop completes (status transitions from `running`)
- **AND** `loop-state.json` contains `total_input_tokens` and `total_cache_create`
- **THEN** the change's orchestration state entry has `context_tokens_end = total_input_tokens + total_cache_create`

#### Scenario: End tokens use total_cache_create not total_cache_read
- **WHEN** inspecting how context_tokens_end is computed
- **THEN** the formula uses `total_cache_create` (tokens written to cache = context created this session)
- **AND** NOT `total_cache_read` (tokens read from cache = prior sessions)

### Requirement: Context window size constant
The monitor SHALL define `CONTEXT_WINDOW_SIZE = 200_000` as a named constant, used to compute utilization percentage: `context_tokens_end / CONTEXT_WINDOW_SIZE * 100`.

#### Scenario: Constant is defined and used
- **WHEN** inspecting `monitor.py`
- **THEN** a constant `CONTEXT_WINDOW_SIZE = 200_000` (or equivalent) exists
- **AND** utilization percentage is derived from it, not hardcoded inline

### Requirement: set-web change list shows context metrics
The set-web change list SHALL display a `ctx` indicator for each change that has `context_tokens_end` in state, showing end tokens and utilization percentage.

#### Scenario: Context metric displayed for completed change
- **WHEN** a change has `context_tokens_end = 150_000` in state
- **THEN** the set-web change list shows something like `ctx: 150K (75%)`

#### Scenario: Context metric shows start→end when both available
- **WHEN** a change has both `context_tokens_start = 40_000` and `context_tokens_end = 150_000`
- **THEN** the set-web change list shows `ctx: 40K → 150K (75%)`

#### Scenario: Context metric absent for changes without data
- **WHEN** a change has no `context_tokens_end` in state (e.g., old state file)
- **THEN** no `ctx` indicator is shown for that change
- **AND** no error or blank column appears

#### Scenario: High context utilization is visually highlighted
- **WHEN** `context_tokens_end / CONTEXT_WINDOW_SIZE >= 0.80`
- **THEN** the context metric is displayed with a warning color or indicator (e.g., orange/red)
