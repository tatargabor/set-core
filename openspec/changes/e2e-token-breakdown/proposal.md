## Why

Token reporting currently flows as a single `total_tokens` number through the entire pipeline (loop-state → orchestration-state → e2e-report). The underlying data source (`wt-usage`) already provides a 4-way breakdown (input, output, cache_read, cache_creation), but `get_current_tokens()` discards this by extracting only `.total_tokens`. This makes it impossible to understand actual capacity usage — a change showing 200K tokens where 150K was cache_read is very different from 200K fresh input.

## What Changes

- `get_current_tokens()` returns all 4 token types instead of just total
- `add_iteration()` stores per-type token counts in loop-state.json
- loop-state.json tracks cumulative totals for each token type
- orchestration-state.json change entries include per-type token fields
- Verifier syncs all 4 token types from loop-state to orchestration-state
- `wt-e2e-report` displays breakdown in both Run Summary and Per-Change table
- All new fields default to 0 for backward compatibility

## Capabilities

### New Capabilities
- `token-breakdown-pipeline`: Propagate input/output/cache_read/cache_create token counts through the entire pipeline from wt-usage to e2e-report

### Modified Capabilities
- `orchestration-token-tracking`: Add per-type token fields to orchestration state and verifier sync

## Impact

- `lib/loop/state.sh` — `get_current_tokens()`, `add_iteration()`, `init_loop_state()`
- `lib/loop/engine.sh` — before/after delta calculation for 4 types
- `lib/orchestration/state.sh` — change init structure, token update logic
- `lib/orchestration/verifier.sh` — token sync from loop-state to orch-state
- `bin/wt-e2e-report` — report output format (summary + per-change table)
- No external API changes, no breaking changes
