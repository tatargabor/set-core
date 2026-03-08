## 1. Loop State — Token Breakdown Foundation

- [x] 1.1 Refactor `get_current_tokens()` in `lib/loop/state.sh` to return JSON string `{"input_tokens":N,"output_tokens":N,"cache_read_tokens":N,"cache_create_tokens":N,"total_tokens":N}` instead of a plain integer. Parse all 5 fields from `wt-usage --format json`. On failure return all-zeros JSON.

- [x] 1.2 Add cumulative per-type fields to `init_loop_state()` in `lib/loop/state.sh`: `total_input_tokens`, `total_output_tokens`, `total_cache_read`, `total_cache_create` (all init to 0) alongside existing `total_tokens`.

- [x] 1.3 Extend `add_iteration()` in `lib/loop/state.sh` to accept and store 4 new per-type token parameters (`input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_create_tokens`) in each iteration entry.

## 2. Engine — Per-Type Delta Calculation

- [x] 2.1 Update `lib/loop/engine.sh` main loop (~line 160-162) to parse `get_current_tokens()` JSON result into individual before-values: `tokens_before_json`, then extract `tokens_before_total`, `in_before`, `out_before`, `cr_before`, `cc_before`.

- [x] 2.2 Update token delta calculation (~line 366-391) to compute per-type deltas from the after-JSON: `in_used=$((in_after - in_before))`, etc. Clamp each to 0. Keep `tokens_used` as the total delta.

- [x] 2.3 Update estimation fallback (~line 373-388) to set per-type values to 0 when using `estimate_tokens_from_files()`.

- [x] 2.4 Update `add_iteration` call (~line 635) to pass the 4 per-type values as additional arguments.

- [x] 2.5 Update `update_loop_state` call (~line 648) to update all 5 cumulative total fields (total_tokens + 4 per-type).

- [x] 2.6 Update chain token tracking (~line 598-606) to compute per-type deltas for chained apply and accumulate them.

- [x] 2.7 Update idle iteration `add_iteration` call (~line 427) to pass 0 for all 4 per-type values.

## 3. Orchestration State — Per-Type Fields

- [x] 3.1 Add `input_tokens: 0`, `output_tokens: 0`, `cache_read_tokens: 0`, `cache_create_tokens: 0` to the change init structure in `lib/orchestration/state.sh` (~line 36-37, next to `tokens_used`).

## 4. Verifier — Sync Per-Type Tokens

- [x] 4.1 In `lib/orchestration/verifier.sh` `check_change_completion()` (~line 408-428), extract all 4 per-type totals from loop-state.json and sync them to orchestration-state via `update_change_field`, applying `tokens_used_prev` accumulation logic to each type.

## 5. E2E Report — Display Breakdown

- [x] 5.1 Update Run Summary in `bin/wt-e2e-report` (~line 158-173) to extract and display per-type totals summed across all changes, with rows for Input, Output, Cache Read, Cache Create.

- [x] 5.2 Update Per-Change Results table (~line 176-189) to add In, Out, CR, CC columns alongside existing Total column. Use K/M formatting.

- [x] 5.3 Update comparison section (~line 214-229) to show per-type deltas vs previous report.

- [x] 5.4 Update summary line (~line 252) to include brief per-type info.
