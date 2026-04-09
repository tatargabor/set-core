## MODIFIED Requirements

### Requirement: Context tokens captured at first iteration completion
The monitor SHALL read `context_tokens_start` from `loop-state.json` after the first iteration completes, computed as the **peak per-call context size** observed during iteration 1: `max(input_tokens + cache_read_input_tokens + cache_creation_input_tokens)` across all Claude API calls in iteration 1's session JSONL files.

The legacy formula (`cache_create_tokens` from iteration 1) MUST NOT be used as a fallback. If iteration 1 has no per-call peak data available (e.g., session JSONL files are missing or unreadable), `context_tokens_start` MUST remain absent rather than defaulting to a misleading cumulative value.

#### Scenario: Start tokens recorded after iteration 1 with peak data available
- **WHEN** a change's loop completes its first iteration
- **AND** the session JSONL files for iteration 1 are readable
- **THEN** the change's orchestration state entry has `context_tokens_start = max(input + cache_read + cache_create)` per individual API call across iteration 1

#### Scenario: Start tokens absent if peak data unavailable
- **WHEN** session JSONL files for iteration 1 are missing or unreadable
- **THEN** `context_tokens_start` is not written to state (field absent, not 0, not derived from cumulative cache_create)

### Requirement: Context tokens captured at loop completion
The monitor SHALL record `context_tokens_end` when a change transitions out of `running` status (to `verifying`, `failed`, or `done`), computed as the **peak per-call context size** observed across the entire loop: `max(input_tokens + cache_read_input_tokens + cache_creation_input_tokens)` across every Claude API call in every iteration's session JSONL files.

The peak represents the largest single-call context the model actually saw during the loop. It MUST NOT be derived from `total_cache_create`, `total_input_tokens`, or any sum that aggregates deltas across multiple API calls — those values describe cache write volume, not context size.

#### Scenario: End tokens recorded as peak per-call context
- **WHEN** a change's loop completes (status transitions from `running`)
- **AND** session JSONL files exist for at least one iteration
- **THEN** the change's orchestration state entry has `context_tokens_end = max(input + cache_read + cache_create)` per individual API call across all iterations

#### Scenario: End tokens never derived from cumulative cache_create
- **WHEN** inspecting how `context_tokens_end` is computed
- **THEN** the formula MUST NOT use `total_cache_create`, MUST NOT use `total_input_tokens + total_cache_create`, and MUST NOT use `max(per-iteration cache_create_tokens)`
- **AND** the formula MUST be the per-call peak as defined above

#### Scenario: End tokens absent for runs without session JSONL data
- **WHEN** no session JSONL files are available for any iteration of the loop
- **THEN** `context_tokens_end` is not written to state

### Requirement: Context window size is dynamic per model
The orchestration state serializer SHALL include a `context_window_size` field per change, derived from the change's `model` field via the existing `_context_window_for_model` resolver in `lib/set_orch/verifier.py`. The default for Claude 4.x models (opus, sonnet, haiku) is 1,000,000 tokens. The legacy 200,000 window is selected only when the model name contains the explicit `[200k]` suffix.

The set-web frontend SHALL compute utilization percentage as `context_tokens_end / context_window_size * 100`, using the `context_window_size` field from the API response. The literal `200_000` MUST NOT appear as a divisor anywhere in the frontend code.

#### Scenario: 1M window for Claude 4.x models by default
- **WHEN** a change runs with `model = "opus"` (or `sonnet`, `haiku`, `claude-opus-4-6`, etc.)
- **THEN** the orchestration state entry has `context_window_size = 1_000_000`

#### Scenario: 200K window for explicit legacy suffix
- **WHEN** a change runs with a model name containing `[200k]`
- **THEN** the orchestration state entry has `context_window_size = 200_000`

#### Scenario: Frontend uses dynamic window from API
- **WHEN** the set-web ChangeTable renders a row with `context_tokens_end = 150_000` and `context_window_size = 1_000_000`
- **THEN** the displayed utilization percentage is `15%`, not `75%`
- **AND** no hardcoded `200_000` literal is used in the calculation

### Requirement: set-web change list shows context metrics with dynamic window
The set-web change list SHALL display a `ctx` indicator for each change that has `context_tokens_end` in state, showing end tokens and utilization percentage computed against the change's `context_window_size`.

#### Scenario: Context metric displayed for completed change
- **WHEN** a change has `context_tokens_end = 150_000` and `context_window_size = 1_000_000` in state
- **THEN** the set-web change list shows something like `ctx: 150K (15%)`

#### Scenario: Context metric shows start→end when both available
- **WHEN** a change has `context_tokens_start = 40_000`, `context_tokens_end = 150_000`, `context_window_size = 1_000_000`
- **THEN** the set-web change list shows `ctx: 40K → 150K (15%)`

#### Scenario: Context metric absent for changes without data
- **WHEN** a change has no `context_tokens_end` in state (e.g., old state file before this change)
- **THEN** no `ctx` indicator is shown for that change
- **AND** no error or blank column appears

#### Scenario: High context utilization is visually highlighted
- **WHEN** `context_tokens_end / context_window_size >= 0.80`
- **THEN** the context metric is displayed with a warning color (e.g., orange/red)
- **AND** the threshold uses the dynamic `context_window_size`, not a hardcoded value
