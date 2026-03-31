## ADDED Requirements

## IN SCOPE
- Measuring baseline context size at session start (before first tool call)
- Categorizing context into components: base (system prompt + CLAUDE.md + rules), memory injection, prompt overhead
- Per-iteration token breakdown stored in loop-state.json
- API endpoint aggregating context data per orchestration run
- Dashboard visualization (stacked bar per change, treemap of components)
- CLI report tool for terminal-based analysis

## OUT OF SCOPE
- Modifying what Claude Code loads (context diet) — that's a separate change
- Real-time streaming context metrics during iteration
- Cross-project comparison (single project scope)
- Modifying Claude Code internals or hook loading behavior

### Requirement: Baseline context measurement at session start
The Ralph loop SHALL measure the baseline context token count after the first Claude API response (before the agent performs substantive work), storing it as `base_context_tokens` in the iteration record.

#### Scenario: First iteration captures baseline
- **WHEN** iteration 1 completes
- **THEN** the iteration record SHALL contain `base_context_tokens` computed as `cache_create_tokens` from that iteration's first API call
- **AND** this value represents the fixed context (system prompt + CLAUDE.md + loaded rules + memory hooks)

#### Scenario: Resumed iterations skip baseline
- **WHEN** iteration N > 1 runs with `--resume`
- **THEN** `base_context_tokens` SHALL be copied from iteration 1's value
- **AND** SHALL NOT be re-measured (resumed sessions inherit prior context)

### Requirement: Per-iteration context breakdown
Each iteration record in `loop-state.json` SHALL include a `context_breakdown` object categorizing token usage.

#### Scenario: Breakdown fields present after iteration
- **WHEN** an iteration completes
- **THEN** the iteration record SHALL contain a `context_breakdown` object with fields:
  - `base_context`: tokens from system prompt + CLAUDE.md + rules (from iteration 1 cache_create or carried forward)
  - `memory_injection`: tokens from hook-injected memory context (estimated from hook output sizes)
  - `prompt_overhead`: tokens from the Ralph loop prompt itself (measured from prompt string length)
  - `tool_output`: tokens consumed by tool call results (computed as `input_tokens - base_context - memory_injection - prompt_overhead`)

#### Scenario: Tool output is the residual category
- **WHEN** computing `tool_output` tokens
- **THEN** the value SHALL be `total_input_tokens - base_context - memory_injection - prompt_overhead`
- **AND** if the result is negative (estimation error), it SHALL be clamped to 0

### Requirement: Memory injection size tracking
The Ralph loop SHALL estimate memory injection size by measuring the output of memory hooks per iteration.

#### Scenario: Hook output measured
- **WHEN** a `UserPromptSubmit` or `PostToolUse` hook fires and returns `<system-reminder>` content
- **THEN** the cumulative size of all hook outputs for this iteration SHALL be tracked
- **AND** stored as `memory_injection` in `context_breakdown` (converted to approximate token count via chars/4 heuristic)

#### Scenario: No memory hooks configured
- **WHEN** the project has no memory hooks in settings.json
- **THEN** `memory_injection` SHALL be 0

### Requirement: Context analysis API endpoint
The set-web API SHALL expose a `/api/<project>/context-analysis` endpoint returning aggregated context data.

#### Scenario: Endpoint returns per-change breakdown
- **WHEN** GET `/api/<project>/context-analysis` is called
- **THEN** the response SHALL contain an array of changes, each with:
  - `change_name`: string
  - `iterations`: number of iterations
  - `base_context_tokens`: number (from iteration 1)
  - `total_input_tokens`: number (sum across iterations)
  - `total_output_tokens`: number (sum across iterations)
  - `context_breakdown_avg`: object with average per-iteration breakdown
  - `efficiency_ratio`: `total_output_tokens / total_input_tokens` (lower = more context overhead)

#### Scenario: Endpoint handles missing data gracefully
- **WHEN** a change has no `context_breakdown` in its loop-state (pre-feature data)
- **THEN** that change SHALL still appear with `context_breakdown_avg: null`
- **AND** basic token totals SHALL still be populated from existing fields

### Requirement: Dashboard context visualization
The set-web dashboard SHALL include a "Context" tab showing context composition.

#### Scenario: Stacked bar chart per change
- **WHEN** the user views the Context tab
- **THEN** a stacked bar chart SHALL show each change's token usage broken down by: base_context (blue), memory_injection (green), prompt_overhead (gray), tool_output (orange)
- **AND** changes SHALL be sorted by total input tokens descending

#### Scenario: Summary statistics displayed
- **WHEN** the Context tab loads
- **THEN** summary cards SHALL show:
  - Total input tokens across all changes
  - Average base context ratio (base_context / total_input across changes)
  - Most expensive change (name + total tokens)
  - Average efficiency ratio

#### Scenario: Comparison across runs
- **WHEN** multiple orchestration runs exist for the project
- **THEN** a dropdown SHALL allow selecting a run
- **AND** the visualization SHALL update to show that run's data

### Requirement: CLI context report
A `set-context-report` CLI tool SHALL generate a terminal-friendly context analysis from loop-state data.

#### Scenario: Report from worktree loop-state
- **WHEN** `set-context-report` is run inside a worktree with `.set/loop-state.json`
- **THEN** it SHALL print a table showing per-iteration breakdown:
  ```
  Iter  Base     Memory   Prompt   Tools    Total    Base%
  1     52K      8K       2K       340K     402K     12.9%
  2     52K      12K      2K       580K     646K     8.0%
  ```

#### Scenario: Report from orchestration directory
- **WHEN** `set-context-report --project <name>` is run
- **THEN** it SHALL aggregate across all change worktrees and print a per-change summary table

#### Scenario: Report identifies optimization targets
- **WHEN** the report runs
- **THEN** it SHALL append a "Recommendations" section identifying:
  - Changes where base_context > 30% of total (potential context diet candidate)
  - Changes where memory_injection > 20% of total (memory over-injection)
  - Changes with efficiency_ratio < 0.05 (very low output per input token)
