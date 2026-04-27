# Loop Token Budget Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Per-change token budget enforcement
The Ralph loop SHALL enforce a maximum token budget per change, pausing for human decision when the budget is exceeded.

#### Scenario: Token budget flag accepted
- **WHEN** `set-loop start` is called with `--token-budget N` (where N is a number in thousands)
- **THEN** the budget SHALL be stored in `loop-state.json` as `token_budget` (in raw token count, i.e., N * 1000)
- **AND** the banner SHALL display the budget: "Budget: {N}K tokens"

#### Scenario: Budget exceeded — human checkpoint
- **WHEN** an iteration completes
- **AND** `total_tokens` in `loop-state.json` exceeds `token_budget`
- **THEN** the loop SHALL update status to `"waiting:budget"`
- **AND** display a checkpoint banner: "Budget checkpoint: {total}K / {budget}K — waiting for human decision"
- **AND** send a desktop notification via `notify-send`
- **AND** enter a wait loop polling `loop-state.json` status every 30 seconds

#### Scenario: Human approves continuation
- **WHEN** the loop is in `waiting:budget` status
- **AND** the status is changed to `"running"` (via `set-loop resume`)
- **THEN** the loop SHALL continue from the next iteration
- **AND** log: "Budget checkpoint approved, continuing"

#### Scenario: Human updates budget
- **WHEN** `set-loop budget <N>` is called while status is `waiting:budget`
- **THEN** `token_budget` SHALL be updated to N * 1000
- **AND** status SHALL be changed to `"running"`
- **AND** the loop SHALL continue from the next iteration

#### Scenario: Human stops loop
- **WHEN** `set-loop stop` is called while status is `waiting:budget`
- **THEN** status SHALL be changed to `"stopped"`
- **AND** the loop SHALL exit cleanly

#### Scenario: Budget not set (default)
- **WHEN** `set-loop start` is called without `--token-budget`
- **THEN** `token_budget` SHALL be `0` in loop-state.json
- **AND** no budget enforcement SHALL occur (unlimited)

#### Scenario: Orchestrator recognizes waiting:budget
- **WHEN** the orchestrator polls a change with status `"waiting:budget"`
- **THEN** it SHALL NOT increment `stall_count`
- **AND** it SHALL NOT attempt to restart the loop
- **AND** it SHALL treat it the same as `"waiting:human"` (requires manual intervention)

#### Scenario: Orchestrator does not set per-change token budget
- **WHEN** the orchestrator dispatches a change via `dispatch_change()`
- **THEN** it SHALL NOT pass `--token-budget` to `set-loop start`
- **AND** the iteration limit (`--max 30`) SHALL serve as the per-change safety net
- **AND** the `set-loop` token budget feature remains available for manual use outside orchestrator context
