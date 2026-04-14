## ADDED Requirements

### Requirement: Smart-retry events

The engine SHALL emit structured events for every retry layer interaction, so that the dashboard and metrics aggregators can reconstruct the retry path per change.

- `RETRY_LAYER_ATTEMPT` — emitted when a layer attempt begins. Payload: `{layer: 1|2|3, gate, change, attempt_num, budget_remaining}`.
- `RETRY_LAYER_RESULT` — emitted when a layer attempt completes. Payload: `{layer, gate, change, outcome: pass|fail|blocked|timeout|scope_violation, duration_ms}`.
- `SUBAGENT_FIX_START` — Layer 2 subagent spawn. Payload: `{gate, change, model, max_turns, allowlist_files}`.
- `SUBAGENT_FIX_END` — Layer 2 subagent return. Payload: `{gate, change, duration_ms, tokens_input, tokens_output, commits_made, outcome, scope_violations: [...]}`.
- `RETRY_CONVERGENCE_FAIL` — convergence threshold reached. Payload: `{change, fingerprints: [{fp, count, title, gate}]}`.
- `INCREMENTAL_REVERIFY` — after a fix, which gates re-ran. Payload: `{change, touched_files, gates_rerun, triggering_layer}`.
- `CONFIG_DRIFT` — yaml edited after directives. Payload: `{yaml_mtime, directives_mtime, delta_secs}`.

#### Scenario: Layer 2 subagent successful fix
- **GIVEN** a Layer 2 attempt for `spec_verify` that succeeds
- **WHEN** the pipeline handles the retry
- **THEN** the following events SHALL be emitted in order:
  1. `RETRY_LAYER_ATTEMPT(layer=2, gate=spec_verify, attempt_num=1, budget_remaining=2)`
  2. `SUBAGENT_FIX_START(gate=spec_verify, model=sonnet, max_turns=15, ...)`
  3. `SUBAGENT_FIX_END(outcome=success, duration_ms=..., commits_made=1)`
  4. `INCREMENTAL_REVERIFY(change=..., touched_files=["src/..."], gates_rerun=["spec_verify"])`
  5. `RETRY_LAYER_RESULT(layer=2, gate=spec_verify, outcome=pass)`

#### Scenario: Convergence triggers Layer 3
- **GIVEN** fingerprint `a3f92c7e` reaches count=3
- **WHEN** the engine detects convergence
- **THEN** `RETRY_CONVERGENCE_FAIL` SHALL be emitted
- **AND** a subsequent `RETRY_LAYER_ATTEMPT(layer=3, ...)` SHALL be emitted within the same pipeline run

### Requirement: Retry-layer dashboard

The web dashboard SHALL display a per-change retry-layer histogram showing how many failures were resolved at each layer. The API endpoint `/api/<project>/retry-layers` SHALL return per-change `{layer_1_success, layer_2_success, layer_3_success, convergence_fails}` counts aggregated from orchestration events.

#### Scenario: Dashboard shows retry layer breakdown
- **GIVEN** a change that had 2 Layer 1 successes, 1 Layer 2 success, 0 Layer 3 attempts, 0 convergence fails
- **WHEN** the API is queried for this change
- **THEN** it SHALL return `{layer_1_success: 2, layer_2_success: 1, layer_3_success: 0, convergence_fails: 0}`
- **AND** the React `RetryLayerHistogram` component SHALL render bars for each layer

#### Scenario: ChangeTable row summary
- **WHEN** the user views the change table
- **THEN** each row with any retries SHALL display a compact "dominant layer" indicator (e.g., "L1×2 L2×1")

### Requirement: Retry metrics

The engine SHALL maintain aggregate metrics in `orchestration-state.extras.metrics`:

- `retry_layer_success_rate` — per-layer success rate over the run: `{layer_1: 0.75, layer_2: 0.60, layer_3: 0.30}`.
- `convergence_failures` — count of convergence events in the run.
- `avg_retries_per_gate` — average `in_gate + subagent + redispatch` attempts per gate across all changes.
- `subagent_tokens_total` — cumulative Layer 2 token usage.

Metrics SHALL update after each pipeline run that involved a retry. Values SHALL be consumable by the dashboard.

#### Scenario: Metrics update after Layer 2 success
- **GIVEN** a Layer 2 attempt for `review` succeeds using 5000 input + 2000 output tokens
- **WHEN** the pipeline commits the retry result
- **THEN** `metrics.subagent_tokens_total` SHALL increase by 7000
- **AND** `metrics.retry_layer_success_rate.layer_2` SHALL be recomputed including this success

#### Scenario: Metrics survive orchestrator restart
- **GIVEN** `metrics` populated during a run
- **WHEN** the orchestrator restarts
- **THEN** `metrics` SHALL be preserved in state (not reset to zero)
- **AND** new events SHALL continue to update the existing values
